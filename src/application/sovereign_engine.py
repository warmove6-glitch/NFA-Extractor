import numpy as np
from datetime import datetime, timedelta

class AntiGravityQuantEngine:
    def __init__(self, risk_trigger_ratio=1.5):
        self.risk_trigger_ratio = risk_trigger_ratio # Flag param em 150% (Distorção aceitável)

    def execute_xgboost_bayesian_proxy(self, dto):
        """Avalia Múltiplas Dimensões: Salto Físico (Gap) e Hipervalorização Contábil Oculta."""
        risk_factor = 0.0
        
        # 1. The Logistic Physics Error: GAP Extremo > Natalidade Natural + Compras
        # Se as saídas superam as entradas sem justificativa biológica (natalidade).
        fator_abismo_quantidade = max(0, dto.total_cabecas_vendidas - dto.total_cabecas_compradas)
        gap_penalty = min(fator_abismo_quantidade / (dto.total_cabecas_compradas + 1), 5.0) * 0.10 # Peso Linear Capado

        # 2. A anomalia profunda (@Sigma's Price Differential Mismatch)
        # O diferencial de preço entre compra e venda (ex: comprar caro e vender barato para dedução fiscal).
        if dto.avg_preco_compra > 0 and dto.avg_preco_venda > 0:
            # Precisamos atualizar o DTO (Note: Pydantic frozen models exigem cuidado, mas aqui o objeto é passado por referência)
            object.__setattr__(dto, 'avg_head_ratio_anomality', dto.avg_preco_compra / dto.avg_preco_venda)
            
            if dto.avg_head_ratio_anomality > self.risk_trigger_ratio:
                # Disritmia financeira causa explosão probabilística sigmoidal
                # Ex: 360% de diferença (ratio 3.6) explode o risco.
                price_mismatch_penalty = 1.0 / (1.0 + np.exp(-(dto.avg_head_ratio_anomality - self.risk_trigger_ratio) * 4))
                risk_factor += price_mismatch_penalty * 0.80 # 80% do peso total da Fraude Contábil.

        # Score Final consolidado (Limite Bayesiano Antigravity)
        score_final = round(min(risk_factor + gap_penalty, 0.9982), 4)
        object.__setattr__(dto, 'score_xgboost_final', score_final)

        # Flag de Severidade
        if dto.score_xgboost_final >= 0.90:
            object.__setattr__(dto, 'fraud_flag_level', "SYSTEMIC_FRAUD_TRIBUTARY")
        elif dto.score_xgboost_final >= 0.70:
            object.__setattr__(dto, 'fraud_flag_level', "HIGH_ALERT")
            
        return dto

    def define_vigilance_cycle(self, risk_score: float, current_stab=1.0) -> tuple[float, datetime]:
        """Calcula o ciclo de vigilância baseado no FSRS."""
        if risk_score > 0.85:
            # Periculosidade Absoluta (@Gama e @Delta: Repressão e Alerta Diário)
            stab = 0.015 
            nxt = datetime.now() + timedelta(days=1)
        else:
            stab = current_stab * 1.5
            nxt = datetime.now() + timedelta(days=int(stab*30))
        return stab, nxt
