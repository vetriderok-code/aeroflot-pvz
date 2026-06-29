# Проброс портов из WSL в Windows

## Проблема
Порты из Docker контейнеров в WSL не пробрасываются автоматически в Windows.

## Решение 1: Использовать IP адрес WSL

1. Узнайте IP адрес WSL:
   ```bash
   wsl hostname -I
   ```

2. Используйте этот IP вместо localhost:
   - http://<WSL_IP>:8888/admin/
   - http://<WSL_IP>:8000/admin/

## Решение 2: Настроить проброс портов в Windows

Создайте файл `portproxy.ps1` и запустите от администратора:

```powershell
# Узнайте IP WSL
$wslIp = (wsl hostname -I).Trim().Split()[0]

# Пробросьте порты
netsh interface portproxy add v4tov4 listenport=8888 listenaddress=0.0.0.0 connectport=8888 connectaddress=$wslIp
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wslIp

# Проверьте
netsh interface portproxy show all
```

## Решение 3: Использовать Docker Desktop

Если установлен Docker Desktop, он автоматически пробрасывает порты. Проверьте настройки Docker Desktop.

## Текущий статус

✅ Telegram бот отключен
✅ Все контейнеры работают:
- API: порт 8000 (внутри WSL)
- Nginx: порт 8888 (внутри WSL)
- PostgreSQL: работает
- Redis: работает

## Быстрый доступ

После настройки проброса портов:
- http://localhost:8888/admin/ (через Nginx)
- http://localhost:8000/admin/ (напрямую к API)

Учетные данные:
- Логин: `admin`
- Пароль: `admin123`












