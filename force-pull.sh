#!/bin/bash
cd "$1" || exit 1

# Пытаемся сделать pull, при неудаче сбрасываем репозиторий
if ! git pull --rebase; then
    echo "⚠ git pull failed, doing hard reset..."
    git fetch origin
    git reset --hard origin/test || exit 1
fi