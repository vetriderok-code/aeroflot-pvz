JAZZMIN_SETTINGS = {
    "site_title": PORTAL_SITE_NAME,
    "site_header": PORTAL_SITE_NAME,
    "site_logo": "images/logo.png",  # если есть логотип
    "welcome_sign": "Добро пожаловать в панель админа",

    "theme": "darkly",  # или "flatly", "cerulean" и т.д.

    "custom_css": "/admin/css/custom_admin.css",

    "topmenu_links": [
        {"name": "Главная", "url": "admin:index"},
        {"name": "Карта", "url": "/"},
        {"name": "Расписание", "url": "/operators/"},
        {"name": "Полеты", "url": "admin:flights_flight_changelist"},
    ],

    "custom_links": {
        "flights": [
            {
                "name": "Расписание",
                "url": "/operators/",
                "icon": "fas fa-calendar-alt",
                "permissions": [],
            },
        ],
    },

    "show_ui_builder": False,
    "navigation_expanded": True,
    "sidebar_nav_small_text": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },

    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "flights": "fas fa-plane",
        "flights.Flight": "fas fa-plane",
        "flights.Pilot": "fas fa-user-pilot",
        "flights.Drone": "fas fa-helicopter",
        "flights.MapLayer": "fas fa-layer-group",
        "flights.OperatorLocation": "fas fa-map-marker-alt",
        "flights.OperatorProfile": "fas fa-headset",
        "flights.OperatorPositionLog": "fas fa-route",
        "flights.LiveFlight": "fas fa-broadcast-tower",
        "flights.DashboardAlert": "fas fa-bell",
        "flights.TelegramFlightReport": "fas fa-paper-plane",
        "flights.ImportProgress": "fas fa-file-import",
        "flights.TargetType": "fas fa-crosshairs",
        "flights.ExplosiveType": "fas fa-bomb",
        "flights.ExplosiveDevice": "fas fa-fire",
        "flights.DirectionType": "fas fa-compass",
        "flights.CorrectiveType": "fas fa-wrench",
    },

    "order_with_respect_to": [
        "flights.OperatorLocation",
        "flights.OperatorProfile",
        "flights.OperatorPositionLog",
        "flights.Pilot",
        "flights.Drone",
        "flights.Flight",
        "flights.LiveFlight",
        "flights.DashboardAlert",
        "flights.TelegramFlightReport",
        "flights.MapLayer",
        "flights.TargetType",
        "flights.ExplosiveType",
        "flights.ExplosiveDevice",
        "flights.DirectionType",
        "flights.CorrectiveType",
        "flights.ImportProgress",
        "auth",
        "axes",
    ],
}