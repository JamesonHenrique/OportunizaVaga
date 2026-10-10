"""bot/cv_fatos.py: the CV summary cannot claim numbers or technologies absent from the candidate's sources."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
from cv_fatos import nao_comprovados  # noqa: E402

FONTES = """# Resumo
Desenvolvedor backend com 2 anos de experiência em Java e Spring Boot, APIs REST e PostgreSQL.
Projeto de automação que reduziu 30% do tempo de triagem.
{"experiencia": {"tecnologias": ["Java", "Spring Boot", "PostgreSQL", "Docker"]}}"""
ALLOW = ["java", "spring boot", "postgresql", "docker", "rest"]


def test_resumo_so_com_fatos_passa():
    r = "Desenvolvedor backend com 2 anos em Java, Spring Boot e Docker; automação que reduziu 30% do tempo."
    assert nao_comprovados(r, FONTES, ALLOW) == []


def test_anos_inventados_sao_barrados():
    assert "5 anos" in nao_comprovados("Mais de 5 anos de experiência com Java.", FONTES, ALLOW)


def test_percentual_inventado_e_barrado():
    assert "40%" in nao_comprovados("Reduzi 40% do custo de infraestrutura.", FONTES, ALLOW)


def test_tecnologia_fora_do_perfil_e_barrada():
    falta = nao_comprovados("Experiência com Java, Kubernetes e Kafka.", FONTES, ALLOW)
    assert "kubernetes" in falta and "kafka" in falta and "java" not in falta


def test_javascript_nao_vira_java_e_vice_versa():
    assert "javascript" in nao_comprovados("Java e JavaScript.", FONTES, ALLOW)


def test_sem_resumo_sem_alarme():
    assert nao_comprovados("", FONTES, ALLOW) == []


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print("ok -", nome)
