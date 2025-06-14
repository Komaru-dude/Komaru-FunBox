#!/bin/bash
cd "$1" || exit 1

# Обновляем локальные ссылки
git fetch origin

# Пытаемся обновить ветку с rebase
if ! git pull --rebase; then
    echo "⚠ git pull failed, doing hard reset..."
    git reset --hard
    git clean -df
fi