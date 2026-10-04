#!/bin/bash
# bot/sites/jooble.sh — 03/10: Cloudflare que nao resolve nem logado (fora_do_rodizio), por isso sondado.
SITE_ID="jooble"
SITE_LABEL="Jooble"
SITE_HOME="https://br.jooble.org"
SEARCH_URL_TEMPLATE="https://br.jooble.org/empregos"
SITE_REMOTE_HINT="403 para curl e o challenge do Cloudflare; se o sonda vir 'bloqueado', nao gaste sessao"
