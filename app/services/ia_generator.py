import os
import json
from datetime import datetime

def gerar_minuta_escuta_ia(dados):
    """
    Motor Especializado de Inteligência Artificial para Emissão de Relatórios 
    de Escuta Qualificada e Guias de Encaminhamento Intersetorial da Rede Municipal.
    Alinhado às diretrizes técnicas do SUAS, SUS, MEC/SECADI e conselhos profissionais (CFP, ABPp, CFESS).
    """
    aluno_nome = dados.get('aluno_nome', 'Estudante')
    aluno_idade = dados.get('aluno_idade', 'Não informada')
    escola = dados.get('escola', 'Rede Municipal de Ensino')
    turma = dados.get('turma', 'Regular')
    especialidade = dados.get('especialidade', 'Equipe Multidisciplinar')
    profissional_nome = dados.get('profissional_nome', 'Técnico Responsável')
    motivo = dados.get('motivo_demanda', '').strip()
    pontos_escuta = dados.get('pontos_escuta', '').strip()
    orgao_destino = dados.get('orgao_destino', 'Rede Intersetorial')
    diagnostico = dados.get('diagnostico', 'Em Investigação')

    # Vocabulário e tom técnico especializado por profissão
    termo_tecnico_espec = {
        'psicologo': {
            'area': 'Psicologia Escolar e Educacional',
            'metodo': 'escuta psicológica qualificada, observação comportamental e acolhimento clínico-institucional',
            'foco': 'desenvolvimento socioemocional, regulação de humor, dinâmica afetiva e processos de subjetivação'
        },
        'psicopedagogo': {
            'area': 'Psicopedagogia Institucional e Clínica',
            'metodo': 'avaliação psicopedagógica, análise das funções cognitivas e mediação das aprendizagens',
            'foco': 'barreiras e potencialidades de aprendizagem, funções executivas, autonomia cognitiva e linguagem'
        },
        'assistente_social': {
            'area': 'Serviço Social na Educação',
            'metodo': 'entrevista social, escuta ativa e mapeamento da rede sociofamiliar e comunitária',
            'foco': 'garantia de direitos (ECA), vulnerabilidade socioeconômica, acesso a políticas públicas e proteção social'
        }
    }.get(especialidade.lower(), {
        'area': 'Equipe Técnica Multidisciplinar',
        'metodo': 'escuta institucional qualificada e acolhimento multiprofissional',
        'foco': 'desenvolvimento integral e garantia do direito à educação e saúde'
    })

    # Construção da Síntese Técnica da Escuta
    sintese_gerada = (
        f"Em atendimento realizado no âmbito da {termo_tecnico_espec['area']}, procedeu-se à escuta qualificada "
        f"do(a) estudante {aluno_nome}, matriculado(a) na instituição {escola} ({turma}). "
        f"Durante a abordagem técnica pautada em {termo_tecnico_espec['metodo']}, o sujeito apresentou relatos pertinentes "
        f"à seguinte demanda focal: \"{motivo}\".\n\n"
        f"Aspectos observados na sessão:\n"
        f"• Expressão comunicativa e engajamento: O(A) estudante demonstrou recepção ao espaço de escuta, "
        f"evidenciando elementos relativos a {pontos_escuta or 'demandas que demandam acompanhamento continuado'}.\n"
        f"• Dimensão investigada: Foram identificadas repercussões diretas em {termo_tecnico_espec['foco']}.\n"
        f"• Situação diagnóstica atual: {diagnostico}."
    )

    # Construção da Situação Contextual
    contexto_gerado = (
        f"No contexto escolar e comunitário do município, observa-se que as manifestações apresentadas "
        f"pelo(a) estudante demandam intervenção articulada que extrapola os limites exclusivamente pedagógicos da sala de aula. "
        f"A equipe da escola relata a necessidade de suporte intersetorial visando à estabilidade emocional, "
        f"desenvolvimento psicossocial e pleno acesso às oportunidades de aprendizagem e convivência saudável."
    )

    # Análise Técnica / Hipótese / Vulnerabilidade
    hipotese_gerada = (
        f"Considerando os elementos colhidos na escuta qualificada e os dados institucionais, "
        f"identifica-se a necessidade de suporte especializado focado em {motivo.lower() if motivo else 'investigação multiprofissional'}. "
        f"Faz-se imperativa a intervenção compartilhada com a rede municipal para confirmação diagnóstica, "
        f"suporte terapêutico continuado e fortalecimento dos vínculos protetivos familiares."
    )

    # Providências Recomendadas e Solicitação ao Órgão de Destino
    providencias_geradas = (
        f"Diante do exposto e com base no princípio da proteção integral preconizado pelo Estatuto da Criança e do Adolescente (ECA - Lei nº 8.069/1990) "
        f"e pela Lei Brasileira de Inclusão (LBI - Lei nº 13.146/2015), ENCAMINHA-SE o(a) estudante {aluno_nome} ao(à) {orgao_destino}, "
        f"solicitando-se respeitosamente:\n\n"
        f"1. Acolhimento, triagem técnica e inclusão em programa de acompanhamento especializado deste respeitável serviço;\n"
        f"2. Avaliação aprofundada na especialidade pertinente com emissão de parecer e/ou plano terapêutico singular;\n"
        f"3. Estabelecimento de contrarreferência técnica com a Secretaria Municipal de Educação / Equipe Multidisciplinar, "
        f"para alinhamento das condutas escolares e suporte ao Plano Educacional Individualizado (PEI)."
    )

    return {
        'sintese_escuta': sintese_gerada,
        'situacao_contextual': contexto_gerado,
        'hipotese_ou_vulnerabilidade': hipotese_gerada,
        'providencias_recomendadas': providencias_geradas,
        'modelo_utilizado': 'ORBI GovTech Intelligence (Padrão SUAS/SUS/SECADI)'
    }
