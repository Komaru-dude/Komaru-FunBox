# vibecoded
import subprocess
from pathlib import Path


def clear_redis_cache():
    print("--- Очистка Redis ---")
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "redis",
        "redis-cli",
        "DEL",
        "check_models_cache",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if "1" in result.stdout:
            print("✓ Ключ 'check_models_cache' успешно удален из Redis.")
        else:
            print(
                "⚠ Команда выполнена, но ключ в Redis не найден (возможно, уже был удален)."
            )
    except subprocess.CalledProcessError as e:
        print(f"✗ Ошибка при вызове docker compose: {e.stderr.strip()}")
    except FileNotFoundError:
        print(
            "✗ Ошибка: Утилита 'docker' не найдена в системе. Скрипт запущен снаружи контейнера?"
        )


def remove_models_json():
    print("\n--- Удаление файла моделей ---")

    # Список путей для проверки по приоритету
    possible_paths = [
        Path("data/models.json"),  # В текущей директории
        Path("../data/models.json"),  # На уровень выше
        Path("/opt/Komaru-FunBox/data/models.json"),  # Абсолютный путь
    ]

    file_deleted = False

    for path in possible_paths:
        # Переводим в абсолютный путь для красивого вывода в лог
        abs_path = path.resolve()

        if abs_path.exists() and abs_path.is_file():
            try:
                abs_path.unlink()
                print(f"✓ Файл успешно удален по пути: {abs_path}")
                file_deleted = True
                break  # Выходим из цикла, так как файл найден и удален
            except Exception as e:
                print(f"✗ Найдено, но не удалось удалить {abs_path}: {e}")
                file_deleted = True
                break
        else:
            print(f"По пути {abs_path} файл не найден...")

    if not file_deleted:
        print("⚠ Ни по одному из путей файл 'models.json' не обнаружен.")


if __name__ == "__main__":
    clear_redis_cache()
    remove_models_json()