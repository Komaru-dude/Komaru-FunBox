#!/bin/bash
cd "$1" || exit 1

# Выбираем ветку в зависимости от наличия файла 'test'
if [ -f test ]; then
    BRANCH="test"
else
    BRANCH="release"
fi

# Переключаемся на нужную ветку
git checkout "$BRANCH" || exit 1

# Обновляем локальные ссылки
git fetch origin

# Пытаемся обновить ветку с rebase
if ! git pull --rebase origin "$BRANCH"; then
    echo "⚠ git pull failed, doing hard reset..."
    git reset --hard "origin/$BRANCH"
    git clean -df
fi