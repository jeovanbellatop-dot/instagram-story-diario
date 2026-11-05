#!/usr/bin/env python3
"""Publica no Instagram o proximo story da fila.

Comandos:
  publicar    publica o primeiro arquivo de fila/ e o move para publicados/
  simulacao   mostra o que seria publicado, sem chamar a API nem mover nada
  verificar   testa o token e mostra a conta, sem publicar nada
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
FILA = RAIZ / "fila"
PUBLICADOS = RAIZ / "publicados"
REGISTRO = PUBLICADOS / "registro.csv"

API = "https://graph.instagram.com/v25.0"
BRASILIA = timezone(timedelta(hours=-3))

# A API de stories so aceita imagem em JPEG.
EXTENSOES_IMAGEM = {".jpg", ".jpeg"}
EXTENSOES_VIDEO = {".mp4", ".mov"}

# A Meta recomenda consultar o status uma vez por minuto, por no maximo 5 minutos.
ESPERA_STATUS_SEGUNDOS = 60
TENTATIVAS_STATUS = 5


class ErroPublicacao(Exception):
    """Falha que deve interromper a execucao com uma mensagem clara."""


def chamar_api(metodo, caminho, token, **params):
    params["access_token"] = token
    dados = urllib.parse.urlencode(params)
    url = f"{API}/{caminho}"
    if metodo == "GET":
        pedido = urllib.request.Request(f"{url}?{dados}")
    else:
        pedido = urllib.request.Request(url, data=dados.encode(), method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            return json.load(resposta)
    except urllib.error.HTTPError as erro:
        corpo = erro.read().decode(errors="replace")
        try:
            detalhe = json.loads(corpo)["error"]
            mensagem = f"{detalhe.get('message')} (codigo {detalhe.get('code')})"
        except (ValueError, KeyError, TypeError):
            mensagem = f"HTTP {erro.code}"
        raise ErroPublicacao(f"A API do Instagram recusou o pedido: {mensagem}") from None
    except urllib.error.URLError as erro:
        raise ErroPublicacao(f"Sem conexao com o Instagram: {erro.reason}") from None


def proximo_da_fila():
    """Retorna o primeiro arquivo aceito, em ordem alfabetica, e quantos ha na fila."""
    aceitos = []
    for arquivo in sorted(FILA.iterdir(), key=lambda a: a.name.lower()):
        if arquivo.name.startswith("."):
            continue
        if arquivo.suffix.lower() in EXTENSOES_IMAGEM | EXTENSOES_VIDEO:
            aceitos.append(arquivo)
        else:
            print(f"::warning::Ignorado (use JPG ou MP4): {arquivo.name}")
    return (aceitos[0] if aceitos else None), len(aceitos)


def url_publica(arquivo):
    repositorio = os.environ.get("GITHUB_REPOSITORY")
    commit = os.environ.get("GITHUB_SHA")
    if not repositorio or not commit:
        raise ErroPublicacao("GITHUB_REPOSITORY e GITHUB_SHA sao necessarios para montar o link.")
    nome = urllib.parse.quote(arquivo.name)
    return f"https://raw.githubusercontent.com/{repositorio}/{commit}/fila/{nome}"


def hoje():
    return datetime.now(BRASILIA).date().isoformat()


def ja_publicou_hoje():
    if not REGISTRO.exists():
        return False
    linhas = REGISTRO.read_text(encoding="utf-8").splitlines()
    return bool(linhas) and linhas[-1].split(",")[0] == hoje()


def aguardar_container(container_id, token):
    for _ in range(TENTATIVAS_STATUS):
        time.sleep(ESPERA_STATUS_SEGUNDOS)
        resposta = chamar_api("GET", container_id, token, fields="status_code,status")
        status = resposta.get("status_code")
        print(f"Status do processamento: {status}")
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED"}:
            raise ErroPublicacao(f"O Instagram rejeitou a midia: {resposta.get('status', status)}")
    raise ErroPublicacao("O Instagram nao terminou de processar a midia em 5 minutos.")


def publicar(arquivo, token):
    conta = chamar_api("GET", "me", token, fields="user_id,username")
    conta_id = conta["user_id"]
    campo = "image_url" if arquivo.suffix.lower() in EXTENSOES_IMAGEM else "video_url"

    container = chamar_api(
        "POST", f"{conta_id}/media", token,
        media_type="STORIES", **{campo: url_publica(arquivo)},
    )
    aguardar_container(container["id"], token)
    publicado = chamar_api("POST", f"{conta_id}/media_publish", token, creation_id=container["id"])
    return publicado["id"], conta.get("username")


def registrar(arquivo, media_id):
    """Roda somente depois de publicar: uma falha antes disso mantem o arquivo na fila."""
    PUBLICADOS.mkdir(exist_ok=True)
    os.replace(arquivo, PUBLICADOS / arquivo.name)
    with REGISTRO.open("a", encoding="utf-8", newline="\n") as registro:
        registro.write(f"{hoje()},{arquivo.name},{media_id}\n")


def obter_token():
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    if not token:
        raise ErroPublicacao("Secret INSTAGRAM_ACCESS_TOKEN nao configurado.")
    return token


def comando_publicar(forcar=False):
    if ja_publicou_hoje() and not forcar:
        print("Ja foi publicado um story hoje. Nada a fazer.")
        return
    arquivo, total = proximo_da_fila()
    if arquivo is None:
        raise ErroPublicacao("A fila esta vazia. Adicione imagens JPG em fila/.")
    media_id, usuario = publicar(arquivo, obter_token())
    registrar(arquivo, media_id)
    print(f"Publicado em @{usuario}: {arquivo.name} (id {media_id}). Restam {total - 1} na fila.")


def comando_simulacao():
    arquivo, total = proximo_da_fila()
    if arquivo is None:
        print("A fila esta vazia.")
        return
    print(f"Seria publicado: {arquivo.name}. Arquivos na fila: {total}.")
    if os.environ.get("GITHUB_SHA"):
        print(f"Link: {url_publica(arquivo)}")


def comando_verificar():
    token = obter_token()
    conta = chamar_api("GET", "me", token, fields="user_id,username,account_type")
    print(f"Conta: @{conta.get('username')} | Tipo: {conta.get('account_type')}")
    limite = chamar_api(
        "GET", f"{conta['user_id']}/content_publishing_limit", token, fields="quota_usage,config",
    )
    print(f"Limite de publicacao: {json.dumps(limite.get('data', limite))}")
    print("Token funcionando.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=["publicar", "simulacao", "verificar"])
    parser.add_argument("--forcar", action="store_true", help="publica mesmo se ja houve story hoje")
    args = parser.parse_args(argv)
    try:
        if args.comando == "publicar":
            comando_publicar(args.forcar)
        elif args.comando == "simulacao":
            comando_simulacao()
        else:
            comando_verificar()
    except ErroPublicacao as erro:
        print(f"::error::{erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
