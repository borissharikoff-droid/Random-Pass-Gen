# Исправление проблем с Railway

## Проблема
Бот крашится на Railway из-за проблем с асинхронным запуском и зависимостями.

## Решения

### 1. Исправлена основная версия (main.py)
- Изменен способ запуска с `asyncio.run()` на `asyncio.get_event_loop().run_until_complete()`
- Исправлена инициализация базы данных
- Добавлена правильная обработка асинхронных функций

### 2. Создана упрощенная версия (main_simple.py)
- Без базы данных (только память)
- Минимальные зависимости
- Гарантированная работа на Railway

## Варианты развертывания

### Вариант A: Основная версия с базой данных
1. Убедитесь что `aiosqlite==0.20.0` установлен
2. Используйте `main.py`
3. Все функции включая админку будут работать

### Вариант B: Упрощенная версия (рекомендуется для быстрого запуска)
1. Переименуйте `main_simple.py` в `main.py`
2. Или измените Procfile на `worker: python main_simple.py`
3. Будет работать без базы данных (история только в памяти)

## Изменения в main.py

### Было:
```python
async def main() -> None:
    await init_database()
    # ...
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
```

### Стало:
```python
def main() -> None:
    # ...
    async def init_db():
        await init_database()
    
    asyncio.get_event_loop().run_until_complete(init_db())
    application.run_polling()

if __name__ == "__main__":
    main()
```

## Рекомендации

1. **Для быстрого запуска**: Используйте `main_simple.py`
2. **Для полного функционала**: Исправленный `main.py`
3. **При проблемах с aiosqlite**: Удалите из requirements.txt и используйте simple версию

## Тестирование локально

```bash
# Тест основной версии
python main.py

# Тест упрощенной версии  
python main_simple.py
```

## Логи для отладки

При проблемах проверьте:
1. Build Logs - ошибки установки зависимостей
2. Deploy Logs - ошибки запуска приложения
3. HTTP Logs - ошибки во время работы

Основные ошибки:
- `ModuleNotFoundError: No module named 'aiosqlite'` - проблема с зависимостями
- `RuntimeError: This event loop is already running` - проблема с asyncio
- `sqlite3.OperationalError` - проблема с базой данных
