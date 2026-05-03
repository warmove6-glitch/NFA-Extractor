from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditoriaMacroSchema(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    contribuinte_id: str = Field(..., pattern=r'^(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})$')
    ano_exercicio: int = Field(default=datetime.now().year)

    # KPIs Físicos
    total_cabecas_compradas: int = Field(default=0, ge=0)
    total_cabecas_vendidas: int = Field(default=0, ge=0)
    gap_qty_animais: int = Field(default=0)

    # KPIs Financeiros
    total_despesa_bruta: float = Field(default=0.0, ge=0.0)
    total_receita_bruta: float = Field(default=0.0, ge=0.0)
    avg_preco_compra: float = Field(default=0.0, ge=0.0)
    avg_preco_venda: float = Field(default=0.0, ge=0.0)

    # Detecção Qualitativa Quantitativa
    avg_head_ratio_anomality: float = Field(default=0.0, description="Distorção Preço Compra/Venda (>1.5 aciona Flag)")
    fraud_flag_level: str = Field(default="NONE") # [NONE, SUSPICIOUS, HIGH_ALERT, SYSTEMIC_FRAUD]
    score_xgboost_final: float = Field(default=0.0, ge=0.0, le=1.0)
