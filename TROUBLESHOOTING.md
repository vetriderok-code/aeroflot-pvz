# Устранение проблем с нестабильностью

## Текущие исправления

1. ✅ Добавлен healthcheck для API
2. ✅ Улучшен entrypoint.sh с обработкой ошибок
3. ✅ Добавлен wget для healthcheck
4. ✅ Создан placeholder для logo.png
5. ✅ Убрана зависимость webserver от healthcheck (временно)

## Возможные причины падений

### 1. Проблемы с базой данных
- Проверьте: `wsl docker-compose logs database`
- Убедитесь, что БД полностью запущена перед API

### 2. Проблемы с памятью
- Gunicorn может падать при нехватке памяти
- Уменьшите количество workers в entrypoint.sh

### 3. Проблемы с миграциями
- Если миграции падают, API не запустится
- Проверьте логи: `wsl docker-compose logs api | grep -i migration`

### 4. Проблемы с зависимостями
- Redis или PostgreSQL могут быть не готовы
- Увеличьте время ожидания в entrypoint.sh

## Команды для диагностики

```bash
# Проверить статус всех контейнеров
wsl docker-compose ps

# Просмотр логов в реальном времени
wsl docker-compose logs -f api

# Проверить использование ресурсов
wsl docker stats

# Проверить последние ошибки
wsl docker-compose logs api | grep -i error | tail -20

# Перезапустить только API
wsl docker-compose restart api

# Полный перезапуск
wsl docker-compose down && wsl docker-compose up -d
```

## Рекомендации

1. Увеличьте timeout для gunicorn если запросы долгие
2. Добавьте больше workers если нагрузка высокая
3. Проверьте логи nginx на ошибки 502/503
4. Убедитесь, что все volumes правильно смонтированы












