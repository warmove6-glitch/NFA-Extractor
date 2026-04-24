import numpy as np
from datetime import datetime, timedelta


class AntiGravityQuantEngine:
    """
    Motor de detecção de fraude tributária baseado em proxy Bayesiano.

    Avalia duas dimensões independentes:
    1. Gap físico-contábil: saídas > entradas sem justificativa biológica.
    2. Inversão de preço: preço médio de compra superior ao preço de venda
       (possível mecanismo de dedução fiscal indevida).

    O score final é um float [0.0, MAX_SCORE], onde valores ≥ THRESHOLD_SYSTEMIC
    indicam fraude sistêmica e ≥ THRESHOLD_HIGH_ALERT indicam alto risco.
    """

    # ── Parâmetros do modelo ──────────────────────────────────────────────────
    # Razão compra/venda acima da qual considera-se anomalia de preço (150%)
    DEFAULT_RISK_TRIGGER_RATIO: float = 1.5

    # Peso do gap de quantidade no score (10% do ratio capado)
    GAP_WEIGHT:      float = 0.10
    # Cap do ratio de gap antes da aplicação do peso
    GAP_RATIO_CAP:   float = 5.0

    # Peso da anomalia de preço no score total (80%)
    PRICE_WEIGHT:    float = 0.80
    # Escala da curva sigmoidal para a penalidade de preço
    PRICE_SIGMOID_SCALE: float = 4.0

    # Teto do score (< 1.0 para preservar semântica probabilística)
    MAX_SCORE: float = 0.9982

    # Limiares de severidade
    THRESHOLD_SYSTEMIC:   float = 0.90  # Fraude sistêmica
    THRESHOLD_HIGH_ALERT: float = 0.70  # Alto risco

    # Limiar de perigo para ciclo de vigilância diária
    THRESHOLD_DAILY_WATCH: float = 0.85

    def __init__(self, risk_trigger_ratio: float = DEFAULT_RISK_TRIGGER_RATIO):
        self.risk_trigger_ratio = risk_trigger_ratio

    # ─────────────────────────────────────────────────────────────────────────

    def execute_xgboost_bayesian_proxy(self, dto):
        """
        Calcula o score de risco e atualiza o DTO in-place via object.__setattr__
        (necessário porque AuditoriaMacroSchema usa frozen=True no Pydantic).

        Retorna o próprio DTO enriquecido com:
            - avg_head_ratio_anomality (float, se aplicável)
            - score_xgboost_final      (float)
            - fraud_flag_level         (str)
        """
        risk_factor = 0.0

        # ── 1. Gap físico: saídas > entradas ─────────────────────────────────
        # Penaliza proporcionalmente ao excedente de cabeças vendidas sobre compradas,
        # normalizado pelo volume de compras (+ 1 para evitar divisão por zero).
  