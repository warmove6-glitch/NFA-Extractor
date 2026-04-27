"""
Testes do parser XML universal — NFSe · NF-e · NFA.

Como adicionar testes para uma nova nota futura:
  1. Copie o XML real (ou um trecho anonimizado) como string em uma fixture abaixo.
  2. Crie um test_parse_<tipo>_<descricao>() usando essa fixture.
  3. Valide os campos críticos com assert_nota_valida() + asserts específicos.

Fixtures disponíveis:
  xml_nfse_real        → NFSe SPED/SEFAZ (Divisa Truck Center, Itumbiara/GO)
  xml_nfe_simples      → NF-e mercadorias (sintético)
  xml_nfa_agropecuaria → NFA agropecuária estadual (sintético)
  xml_sem_assinatura   → NFSe sem bloco <Signature> (pre-limpo)
  xml_invalido         → XML malformado (testa robustez)
"""

from __future__ import annotations

import pytest
from src.domain.xml_parser import (
    parse_xml,
    parse_xml_lote,
    resumo_lote_para_agentes,
    NotaFiscalXML,
    TIPO_NFSE,
    TIPO_NFE,
    TIPO_NFA,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — XMLs representativos
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def xml_nfse_real() -> bytes:
    """NFSe SPED real (Divisa Truck Center, Itumbiara/GO, nNFSe=4866).

    Fonte: arquivo enviado pelo usuário em 2026-04-26.
    Emitente: DIVISA TRUCK CENTER LTDA (CNPJ 39558194000180)
    Tomador : BOIVIP TRANSPORTE DE BOVINOS LTDA (CNPJ 61411585000127)
    Serviço : Manutenção de veículo — cTribNac 140101
    Valor   : R$ 1.240,00 | ISSQN 3% = R$ 37,20
    """
    return b"""<?xml version="1.0" encoding="utf-8"?>
<NFSe versao="1.00" xmlns="http://www.sped.fazenda.gov.br/nfse">
<infNFSe Id="NFS52115031239558194000180000000000486626023714913456">
<xLocEmi>ITUMBIARA - GO</xLocEmi>
<xLocPrestacao>ITUMBIARA - GO</xLocPrestacao>
<nNFSe>4866</nNFSe>
<cLocIncid>5211503</cLocIncid>
<xLocIncid>ITUMBIARA - GO</xLocIncid>
<xTribNac>Servico codigo 140101</xTribNac>
<verAplic>1.00</verAplic>
<ambGer>1</ambGer>
<tpEmis>2</tpEmis>
<cStat>100</cStat>
<dhProc>2026-02-12T18:03:16-03:00</dhProc>
<nDFSe>4866</nDFSe>
<emit>
  <CNPJ>39558194000180</CNPJ>
  <IM>604394</IM>
  <xNome>DIVISA TRUCK CENTER LTDA</xNome>
  <xFant>DIVISA TRUCK CENTER</xFant>
</emit>
<valores>
  <vCalcDR>0.00</vCalcDR>
  <vBC>1240.00</vBC>
  <pAliqAplic>3.00</pAliqAplic>
  <vISSQN>37.20</vISSQN>
  <vLiq>1240.00</vLiq>
</valores>
<DPS versao="1.00">
  <infDPS Id="DPS521150323955819400018000001000000000004866">
    <tpAmb>1</tpAmb>
    <dhEmi>2026-02-12T18:03:16-03:00</dhEmi>
    <verAplic>1.00</verAplic>
    <serie>00001</serie>
    <nDPS>4866</nDPS>
    <dCompet>2026-02-12</dCompet>
    <tpEmit>1</tpEmit>
    <cLocEmi>5211503</cLocEmi>
    <prest>
      <CNPJ>39558194000180</CNPJ>
      <IM>604394</IM>
      <regTrib>
        <opSimpNac>3</opSimpNac>
        <regApTribSN>1</regApTribSN>
        <regEspTrib>0</regEspTrib>
      </regTrib>
    </prest>
    <toma>
      <CNPJ>61411585000127</CNPJ>
      <xNome>BOIVIP TRANSPORTE DE BOVINOS LTDA</xNome>
    </toma>
    <serv>
      <cServ>
        <cTribNac>140101</cTribNac>
        <xDescServ>MANUTENCAO VEICULO PLACA EZU-3H53</xDescServ>
      </cServ>
    </serv>
    <valores>
      <vServPrest>
        <vServ>1240.00</vServ>
      </vServPrest>
      <trib>
        <tribMun>
          <tribISSQN>1</tribISSQN>
          <tpRetISSQN>1</tpRetISSQN>
          <pAliq>3.00</pAliq>
        </tribMun>
      </trib>
    </valores>
  </infDPS>
</DPS>
</infNFSe>
</NFSe>"""


@pytest.fixture
def xml_nfe_simples() -> bytes:
    """NF-e de mercadorias — sintético baseado no schema portalfiscal 4.00.

    Emitente : AGROPECUARIA EXEMPLO SA (CNPJ 12345678000195) — CRT=1 Simples
    Destinatário: FRIGORIFICO MODELO LTDA (CNPJ 98765432000100)
    Produto : BOVI BOVINO — 10 cab × R$ 3.500 = R$ 35.000
    ICMS    : BC R$ 35.000 | 12% = R$ 4.200
    """
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
    <infNFe versao="4.00">
      <ide>
        <cUF>52</cUF>
        <nNF>1001</nNF>
        <serie>1</serie>
        <dhEmi>2026-03-10T09:00:00-03:00</dhEmi>
        <natOp>VENDA DE GADO BOVINO</natOp>
        <CFOP>5101</CFOP>
      </ide>
      <emit>
        <CNPJ>12345678000195</CNPJ>
        <xNome>AGROPECUARIA EXEMPLO SA</xNome>
        <enderEmit>
          <xMun>GOIANIA</xMun>
          <UF>GO</UF>
        </enderEmit>
        <IE>1234567890</IE>
        <CRT>1</CRT>
      </emit>
      <dest>
        <CNPJ>98765432000100</CNPJ>
        <xNome>FRIGORIFICO MODELO LTDA</xNome>
      </dest>
      <det nItem="1">
        <prod>
          <cProd>BOV001</cProd>
          <xProd>BOVINO NELORE MACHO</xProd>
          <qCom>10.000</qCom>
          <vUnCom>3500.00</vUnCom>
          <vProd>35000.00</vProd>
          <uCom>CAB</uCom>
          <CFOP>5101</CFOP>
        </prod>
        <imposto>
          <ICMS>
            <ICMS00>
              <pICMS>12.00</pICMS>
              <vICMS>4200.00</vICMS>
            </ICMS00>
          </ICMS>
        </imposto>
      </det>
      <total>
        <ICMSTot>
          <vBC>35000.00</vBC>
          <vICMS>4200.00</vICMS>
          <vNF>35000.00</vNF>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>"""


@pytest.fixture
def xml_nfa_agropecuaria() -> bytes:
    """NFA estadual — sintético baseado em schema GONFAe/Goiás.

    Emitente : FAZENDA BOA ESPERANCA (CPF 012.345.678-90)
    Destinatário: FRIGORIFICO REGIONAL LTDA
    Produto : 50 novilhos — R$ 175.000 | ICMS 12% = R$ 21.000
    """
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<NFA>
  <infNFA>
    <ide>
      <nNF>5500</nNF>
      <serie>1</serie>
      <dEmi>2026-01-15</dEmi>
      <natOp>VENDA DE GADO BOVINO</natOp>
      <CFOP>5101</CFOP>
    </ide>
    <emit>
      <CPF>01234567890</CPF>
      <xNome>FAZENDA BOA ESPERANCA</xNome>
      <IE>123456789</IE>
      <enderEmit>
        <xMun>JATAI</xMun>
        <UF>GO</UF>
      </enderEmit>
    </emit>
    <dest>
      <CNPJ>55566677000100</CNPJ>
      <xNome>FRIGORIFICO REGIONAL LTDA</xNome>
    </dest>
    <det nItem="1">
      <prod>
        <xProd>NOVILHO NELORE</xProd>
        <qCom>50</qCom>
        <vUnCom>3500.00</vUnCom>
        <vProd>175000.00</vProd>
        <uCom>CAB</uCom>
      </prod>
    </det>
    <total>
      <ICMSTot>
        <vBC>175000.00</vBC>
        <vICMS>21000.00</vICMS>
        <vNF>175000.00</vNF>
      </ICMSTot>
    </total>
  </infNFA>
</NFA>"""


@pytest.fixture
def xml_invalido() -> bytes:
    """XML malformado — para validar tratamento de erros."""
    return b"<NFSe><unclosed>"


# ─────────────────────────────────────────────────────────────────────────────
# Helper de validação genérica
# ─────────────────────────────────────────────────────────────────────────────

def assert_nota_valida(nota: NotaFiscalXML) -> None:
    """Asserts mínimos válidos para qualquer nota fiscal parseada."""
    assert nota.tipo in (TIPO_NFSE, TIPO_NFE, TIPO_NFA), f"Tipo inválido: {nota.tipo}"
    assert nota.numero, "número não pode ser vazio"
    assert nota.data_emissao, "data de emissão não pode ser vazia"
    assert nota.emitente_nome, "emitente não pode ser vazio"
    assert nota.emitente_doc, "CNPJ/CPF do emitente não pode ser vazio"
    assert nota.valor_total > 0, f"valor_total deve ser positivo, got {nota.valor_total}"
    assert nota.tokens_resumo > 0, "tokens_resumo deve ser calculado após parse"


# ─────────────────────────────────────────────────────────────────────────────
# Testes — NFSe
# ─────────────────────────────────────────────────────────────────────────────

class TestNFSe:
    def test_tipo_detectado(self, xml_nfse_real):
        nota = parse_xml(xml_nfse_real)
        assert nota.tipo == TIPO_NFSE

    def test_campos_obrigatorios(self, xml_nfse_real):
        nota = parse_xml(xml_nfse_real)
        assert_nota_valida(nota)

    def test_numero_correto(self, xml_nfse_real):
        nota = parse_xml(xml_nfse_real)
        assert nota.numero == "4866"

    def test_data_emissao(self, xml_nfse_real):
        nota = parse_xml(xml_nfse_real)
        assert nota.data_emissao == "2026-02-12"

    def test_municipio_uf(self, xml_nfse_real):
        nota = parse_xml(xml_nfse_real)
        assert nota.municipio == "ITUMBIARA"
        assert nota.uf == "GO"

    def test_emitente(self, xml_nfse_real):
        nota = parse_xml(xml_nfse_real)
        assert "DIVISA TRUCK CENTER" in nota.emitente_nome
        assert nota.emitente_doc == "39558194000180"
        assert nota.emitente_ie == "604394"

    def test_regime_simples(self, xml_nfse_real):
        """opSimpNac=3 → Simples Nacional."""
        nota = parse_xml(xml_nfse_real)
        assert "Simples" in nota.emitente_regime

    def test_tomador(self, xml_nfse_real):
        nota = parse_xml(xml_nfse_real)
        assert "BOIVIP" in nota.tomador_nome
        assert nota.tomador_doc == "61411585000127"

    def test_valores_issqn(self, xml_nfse_real):
        nota = parse_xml(xml_nfse_real)
        assert nota.valor_total == pytest.approx(1240.0)
        assert nota.valor_bc   == pytest.approx(1240.0)
        assert nota.aliquota   == pytest.approx(3.0)
        assert nota.valor_imposto == pytest.approx(37.2)
        assert nota.tipo_imposto == "ISSQN"

    def test_codigo_fiscal(self, xml_nfse_real):
        nota = parse_xml(xml_nfse_real)
        assert nota.codigo_fiscal == "140101"

    def test_tokens_compactos(self, xml_nfse_real):
        """Resumo deve ter menos de 150 tokens (eficiência de custo)."""
        nota = parse_xml(xml_nfse_real)
        assert nota.tokens_resumo < 150, f"tokens_resumo={nota.tokens_resumo} excede limite"

    def test_aceita_bytes_e_string(self, xml_nfse_real):
        nota_bytes = parse_xml(xml_nfse_real)
        nota_str   = parse_xml(xml_nfse_real.decode("utf-8"))
        assert nota_bytes.numero == nota_str.numero
        assert nota_bytes.valor_total == nota_str.valor_total

    def test_assinatura_x509_removida(self, xml_nfse_real):
        """Garante que o bloco Signature não vaza para os campos parseados."""
        xml_com_sig = xml_nfse_real + b"""
<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
  <SignedInfo><Reference URI="#fake"/></SignedInfo>
  <SignatureValue>BASE64FAKECERTIFICADO</SignatureValue>
  <KeyInfo><X509Data><X509Certificate>MIIFAKE</X509Certificate></X509Data></KeyInfo>
</Signature>"""
        nota = parse_xml(xml_com_sig)
        assert "MIIFAKE" not in nota.emitente_nome
        assert "BASE64" not in nota.natureza
        assert nota.numero == "4866"


# ─────────────────────────────────────────────────────────────────────────────
# Testes — NF-e
# ─────────────────────────────────────────────────────────────────────────────

class TestNFe:
    def test_tipo_detectado(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples)
        assert nota.tipo == TIPO_NFE

    def test_campos_obrigatorios(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples)
        assert_nota_valida(nota)

    def test_numero_e_serie(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples)
        assert nota.numero == "1001"
        assert nota.serie  == "1"

    def test_data_emissao(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples)
        assert nota.data_emissao == "2026-03-10"

    def test_emitente(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples)
        assert "AGROPECUARIA EXEMPLO" in nota.emitente_nome
        assert nota.emitente_doc == "12345678000195"
        assert "Simples" in nota.emitente_regime  # CRT=1

    def test_destinatario(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples)
        assert "FRIGORIFICO MODELO" in nota.tomador_nome
        assert nota.tomador_doc == "98765432000100"

    def test_natureza_cfop(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples)
        assert "BOVINO" in nota.natureza.upper()
        assert nota.codigo_fiscal == "5101"

    def test_icms(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples)
        assert nota.valor_total   == pytest.approx(35000.0)
        assert nota.valor_bc      == pytest.approx(35000.0)
        assert nota.valor_imposto == pytest.approx(4200.0)
        assert nota.tipo_imposto  == "ICMS"

    def test_itens_extraidos(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples, modo_resumo="completo")
        assert len(nota.itens) == 1
        item = nota.itens[0]
        assert item.quantidade   == pytest.approx(10.0)
        assert item.vlr_unitario == pytest.approx(3500.0)
        assert item.vlr_total    == pytest.approx(35000.0)
        assert item.unidade      == "CAB"


# ─────────────────────────────────────────────────────────────────────────────
# Testes — NFA Agropecuária
# ─────────────────────────────────────────────────────────────────────────────

class TestNFA:
    def test_tipo_detectado(self, xml_nfa_agropecuaria):
        nota = parse_xml(xml_nfa_agropecuaria)
        assert nota.tipo == TIPO_NFA

    def test_campos_obrigatorios(self, xml_nfa_agropecuaria):
        nota = parse_xml(xml_nfa_agropecuaria)
        assert_nota_valida(nota)

    def test_numero(self, xml_nfa_agropecuaria):
        nota = parse_xml(xml_nfa_agropecuaria)
        assert nota.numero == "5500"

    def test_emitente_cpf(self, xml_nfa_agropecuaria):
        """Produtor rural pode usar CPF (não CNPJ)."""
        nota = parse_xml(xml_nfa_agropecuaria)
        assert "FAZENDA BOA ESPERANCA" in nota.emitente_nome
        assert nota.emitente_doc == "01234567890"

    def test_valor_e_icms(self, xml_nfa_agropecuaria):
        nota = parse_xml(xml_nfa_agropecuaria)
        assert nota.valor_total   == pytest.approx(175000.0)
        assert nota.valor_imposto == pytest.approx(21000.0)
        assert nota.tipo_imposto  == "ICMS"


# ─────────────────────────────────────────────────────────────────────────────
# Testes — Robustez e casos-limite
# ─────────────────────────────────────────────────────────────────────────────

class TestRobustez:
    def test_xml_invalido_levanta_value_error(self, xml_invalido):
        with pytest.raises(ValueError, match="malformado"):
            parse_xml(xml_invalido)

    def test_lote_vazio(self):
        resultado = resumo_lote_para_agentes([])
        assert "Nenhuma" in resultado

    def test_lote_com_multiplos_tipos(self, xml_nfse_real, xml_nfe_simples, xml_nfa_agropecuaria):
        lote = parse_xml_lote([xml_nfse_real, xml_nfe_simples, xml_nfa_agropecuaria])
        assert len(lote) == 3
        tipos = {n.tipo for n in lote}
        assert TIPO_NFSE in tipos
        assert TIPO_NFE  in tipos
        assert TIPO_NFA  in tipos

    def test_resumo_lote_contem_totais(self, xml_nfse_real, xml_nfe_simples):
        lote = parse_xml_lote([xml_nfse_real, xml_nfe_simples])
        bloco = resumo_lote_para_agentes(lote)
        assert "LOTE" in bloco
        assert "Total" in bloco
        # Soma: 1240 + 35000 = 36240
        # Python formata com vírgula como separador de milhar: R$36,240.00
        assert "36,240" in bloco

    def test_lote_ignora_xml_invalido(self, xml_nfse_real, xml_invalido):
        """parse_xml_lote não deve abortar se um arquivo é inválido."""
        lote = parse_xml_lote([xml_nfse_real, xml_invalido])
        assert len(lote) == 1          # inválido descartado sem crash
        assert lote[0].tipo == TIPO_NFSE

    def test_resumo_auditoria_modo_completo(self, xml_nfe_simples):
        nota = parse_xml(xml_nfe_simples, modo_resumo="completo")
        resumo = nota.resumo_auditoria("completo")
        assert "Itens" in resumo
        assert "BOVINO" in resumo.upper()

    def test_encoding_utf8(self):
        """Acentos em xNome não devem causar erro."""
        xml = b"""<NFSe versao="1.00" xmlns="http://www.sped.fazenda.gov.br/nfse">
<infNFSe><xLocEmi>S\xc3\xa3o Paulo - SP</xLocEmi>
<nNFSe>99</nNFSe>
<emit><CNPJ>11222333000181</CNPJ><xNome>Presta\xc3\xa7\xc3\xa3o Servi\xc3\xa7os Ltda</xNome><IM>999</IM></emit>
<valores><vBC>500.00</vBC><pAliqAplic>5.00</pAliqAplic><vISSQN>25.00</vISSQN><vLiq>500.00</vLiq></valores>
<DPS versao="1.00"><infDPS><dhEmi>2026-04-01T10:00:00-03:00</dhEmi><serie>1</serie>
<toma><CNPJ>44555666000177</CNPJ><xNome>Cliente Final SA</xNome></toma>
<serv><cServ><cTribNac>010101</cTribNac><xDescServ>Consultoria</xDescServ></cServ></serv>
<valores><vServPrest><vServ>500.00</vServ></vServPrest></valores>
</infDPS></DPS></infNFSe></NFSe>"""
        nota = parse_xml(xml)
        assert "Prest" in nota.emitente_nome or nota.emitente_nome != ""
        assert nota.valor_total == pytest.approx(500.0)
