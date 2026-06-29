# Проблема с получением SSL сертификатов

## Проблема

Let's Encrypt не может подключиться к серверу на порту 80:
```
Timeout during connect (likely firewall problem)
```

## Причины

1. **Порт 80 закрыт в firewall** на сервере
2. **Порт 80 не проброшен** через роутер/маршрутизатор
3. **Проблемы с маршрутизацией** на уровне провайдера

## Решения

### Вариант 1: Открыть порт 80 в firewall (рекомендуется)

Если у вас есть доступ к серверу, откройте порт 80:

**Для Ubuntu/Debian (ufw):**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

**Для CentOS/RHEL (firewalld):**
```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

**Для iptables:**
```bash
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### Вариант 2: Использовать DNS challenge (если порт 80 недоступен)

DNS challenge не требует открытого порта 80:

```powershell
.\get-ssl-dns-challenge.ps1 -Email "adminsito@mail.ru"
```

Или напрямую:
```powershell
docker run -it --rm -v "$(pwd)/certbot/conf:/etc/letsencrypt" certbot/certbot certonly --manual --preferred-challenges dns --email adminsito@mail.ru --agree-tos --no-eff-email -d aeroflot-pvz.ru -d www.aeroflot-pvz.ru
```

Certbot попросит добавить TXT запись в DNS. После добавления нажмите Enter.

### Вариант 3: Проверить доступность порта 80

Проверьте доступность порта извне:

```bash
# С другого сервера или через онлайн сервис
curl -I http://aeroflot-pvz.ru
telnet aeroflot-pvz.ru 80
```

Или используйте онлайн инструменты:
- https://www.yougetsignal.com/tools/open-ports/
- https://canyouseeme.org/

## Проверка конфигурации nginx

Убедитесь что nginx правильно настроен для обслуживания файлов certbot:

```nginx
location /.well-known/acme-challenge/ {
    root /var/www/certbot;
    try_files $uri =404;
}
```

Этот блок должен быть **перед** другими location блоками.

## После открытия порта 80

После открытия порта 80 попробуйте снова получить сертификаты:

```powershell
docker run --rm -v "$(pwd)/certbot/conf:/etc/letsencrypt" -v "$(pwd)/certbot/www:/var/www/certbot" certbot/certbot certonly --webroot --webroot-path=/var/www/certbot --email adminsito@mail.ru --agree-tos --no-eff-email --non-interactive -d aeroflot-pvz.ru -d www.aeroflot-pvz.ru
```

## Рекомендация

Для продакшена лучше использовать webroot метод (требует открытый порт 80), так как он позволяет автоматически обновлять сертификаты.

DNS challenge подходит для случаев, когда порт 80 недоступен, но требует ручного обновления DNS записей при каждом обновлении сертификата.
