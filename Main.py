import telebot
import sqlite3
import time
import random
import threading
import math

TOKEN = '8539716689:AAEZh2dVddEMMsU4cLNs0JPgqosyeMfXX_8'
ADMIN_IDS = [6115517123, 2046462689, 7787565361]
ALLOWED_GROUP_IDS = [-1003880025896, -1003790960557]

bot = telebot.TeleBot(TOKEN)

# ==============================================================
# --- ФИЛЬТР ГРУППЫ ---
# ==============================================================
def group_only(func):
    def wrapper(message):
        if message.chat.id not in ALLOWED_GROUP_IDS:
            return
        func(message)
    return wrapper

# ==============================================================
# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
# ==============================================================
def init_db():
    conn = sqlite3.connect('aurelia_economy.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            balance INTEGER DEFAULT 1000,
            level INTEGER DEFAULT 1,
            last_cash REAL DEFAULT 0,
            troops INTEGER DEFAULT 0,
            last_draft REAL DEFAULT 0,
            ep INTEGER DEFAULT 0,
            last_ep REAL DEFAULT 0,
            banned INTEGER DEFAULT 0
        )
    ''')

    migrations = [
        "ALTER TABLE users ADD COLUMN troops INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN last_draft REAL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN ep INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN last_ep REAL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0",
    ]
    for m in migrations:
        try:
            cursor.execute(m)
        except sqlite3.OperationalError:
            pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            display_name TEXT,
            cost INTEGER,
            income_per_hour INTEGER,
            description TEXT,
            ep_per_12h INTEGER DEFAULT 0
        )
    ''')
    try:
        cursor.execute("ALTER TABLE business_types ADD COLUMN ep_per_12h INTEGER DEFAULT 0")
    except:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            business_name TEXT,
            quantity INTEGER DEFAULT 1,
            UNIQUE(user_id, business_name)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_assets (
            name TEXT PRIMARY KEY,
            display_name TEXT,
            price REAL,
            base_price REAL,
            last_updated REAL DEFAULT 0,
            emoji TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_portfolio (
            user_id INTEGER,
            asset_name TEXT,
            quantity REAL DEFAULT 0,
            avg_buy_price REAL DEFAULT 0,
            PRIMARY KEY (user_id, asset_name)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS military_types (
            name TEXT PRIMARY KEY,
            display_name TEXT,
            steel_cost INTEGER,
            money_cost INTEGER,
            description TEXT,
            power_value INTEGER DEFAULT 1
        )
    ''')
    try:
        cursor.execute("ALTER TABLE military_types ADD COLUMN power_value INTEGER DEFAULT 1")
    except:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_military (
            user_id INTEGER,
            unit_name TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, unit_name)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_extractors (
            user_id INTEGER PRIMARY KEY,
            quantity INTEGER DEFAULT 0,
            last_extract REAL DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tech_types (
            name TEXT PRIMARY KEY,
            display_name TEXT,
            max_level INTEGER DEFAULT 5,
            ep_cost_per_level INTEGER,
            description TEXT,
            effect TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tech (
            user_id INTEGER,
            tech_name TEXT,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, tech_name)
        )
    ''')

    conn.commit()

    # ЦЕНЫ УДВОЕНЫ (x2 от оригинала)
    businesses = [
        ('farm',      '🌾 Ферма',           4000,   40,  'Небольшой, но надёжный источник дохода', 10),
        ('factory',   '🏭 Завод',           10000,  120, 'Производит товары, стабильный доход + ОЭ', 50),
        ('mine',      '⛏️ Шахта',           16000,  220, 'Добывает ресурсы Аурелии, даёт ОЭ', 50),
        ('casino',    '🎰 Казино',          30000,  450, 'Огромный доход, требует больших вложений', 20),
        ('bank_biz',  '🏦 Частный банк',    60000,  950, 'Элитный бизнес с максимальным пассивным доходом', 30),
    ]
    cursor.executemany(
        'INSERT OR IGNORE INTO business_types (name, display_name, cost, income_per_hour, description, ep_per_12h) VALUES (?,?,?,?,?,?)',
        businesses
    )
    for name, _, _, _, _, ep in businesses:
        cursor.execute("UPDATE business_types SET ep_per_12h = ? WHERE name = ?", (ep, name))

    assets = [
        ('oil',    '🛢️ Нефть',   100.0, 100.0, '🛢️'),
        ('gold',   '🥇 Золото',  500.0, 500.0, '🥇'),
        ('steel',  '⚙️ Сталь',   80.0,  80.0,  '⚙️'),
        ('aur',    '💎 Аурит',   300.0, 300.0, '💎'),
    ]
    cursor.executemany(
        'INSERT OR IGNORE INTO market_assets (name, display_name, price, base_price, emoji) VALUES (?,?,?,?,?)',
        assets
    )

    # СТОИМОСТЬ ТЕХНИКИ УДВОЕНА + добавлены очки мощи
    military = [
        ('rifle',      '🔫 Винтовки',        2,    200,    'Базовое вооружение пехоты', 1),
        ('tank',       '🛡️ Танки',           50,   10000,  'Тяжелая бронетехника для прорыва', 50),
        ('artillery',  '💥 Артиллерия',      80,   16000,  'Дальнобойная огневая поддержка', 40),
        ('aa_gun',     '🎯 ПВО',             60,   14000,  'Зенитные установки для защиты от авиации', 30),
        ('plane',      '✈️ Истребители',     120,  30000,  'Господство в воздухе', 80),
        ('bomber',     '💣 Бомбардировщики', 180,  50000,  'Стратегические удары по объектам', 100),
        ('bomb',       '💥 Авиабомбы',       20,   3000,   'Боеприпасы для бомбардировщиков', 5),
        ('ship',       '🚢 Эсминцы',         200,  50000,  'Основа военно-морского флота', 120),
        ('submarine',  '🛥️ Подлодки',        150,  40000,  'Скрытые морские удары', 100),
        ('carrier',    '⛴️ Авианосцы',       1000, 300000, 'Полное господство в океане', 500),
    ]
    cursor.executemany(
        'INSERT OR IGNORE INTO military_types (name, display_name, steel_cost, money_cost, description, power_value) VALUES (?,?,?,?,?,?)',
        military
    )
    for name, _, _, _, _, power in military:
        cursor.execute("UPDATE military_types SET power_value = ? WHERE name = ?", (power, name))

    tech_types = [
        ('finance',    '💹 Финансовый менеджмент', 5, 100, '+10% к доходу /cash за каждый уровень',           '+10% cash per level'),
        ('logistics',  '🚛 Логистика',            5, 150, '-10% к содержанию армии за каждый уровень',       '-10% maintenance per level'),
        ('metallurgy', '🔩 Металлургия',           5, 200, '-8% к расходу стали при крафте за каждый уровень','-8% steel cost per level'),
        ('engineering','⚙️ Инженерия',            5, 200, '-8% к денежному расходу при крафте за уровень',   '-8% money cost per level'),
        ('military_sc','🎖️ Военная наука',        5, 250, '+15% к боевой мощи за каждый уровень',           '+15% military power per level'),
        ('industry',   '🏗️ Индустриализация',     5, 180, '+20% к генерации ОЭ за каждый уровень',          '+20% EP per level'),
        ('energy',     '⚡ Энергетика',           5, 220, '-10% к расходу нефти танками за уровень',         '-10% oil consumption per level'),
    ]
    cursor.executemany(
        'INSERT OR IGNORE INTO tech_types (name, display_name, max_level, ep_cost_per_level, description, effect) VALUES (?,?,?,?,?,?)',
        tech_types
    )

    conn.commit()
    conn.close()

init_db()

# ==============================================================
# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
# ==============================================================
def db_query(query, args=(), fetchone=False):
    conn = sqlite3.connect('aurelia_economy.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(query, args)
    if query.strip().upper().startswith("SELECT"):
        result = cursor.fetchone() if fetchone else cursor.fetchall()
    else:
        conn.commit()
        result = None
    conn.close()
    return result

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_banned(user_id):
    result = db_query("SELECT banned FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    return result and result[0] == 1

def get_price_arrow(price, base_price):
    if price > base_price * 1.1:
        return "📈"
    elif price < base_price * 0.9:
        return "📉"
    return "➡️"

def get_user_tech_level(user_id, tech_name):
    result = db_query("SELECT level FROM user_tech WHERE user_id = ? AND tech_name = ?",
                      (user_id, tech_name), fetchone=True)
    return result[0] if result else 0

def get_tank_oil_consumption(tank_count):
    """Возвращает расход нефти за 3-часовой период по скобкам."""
    if tank_count <= 0:
        return 0.0
    bracket = math.ceil(tank_count / 50)
    return bracket * 0.1

def calc_military_power(user_id):
    units = db_query('''
        SELECT um.unit_name, um.quantity, mt.power_value
        FROM user_military um
        JOIN military_types mt ON um.unit_name = mt.name
        WHERE um.user_id = ? AND um.quantity > 0
    ''', (user_id,))

    troops_row = db_query("SELECT troops FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    troop_count = troops_row[0] if troops_row else 0

    power = troop_count
    for unit_name, qty, pv in (units or []):
        power += qty * pv

    mil_tech = get_user_tech_level(user_id, 'military_sc')
    power = int(power * (1 + mil_tech * 0.15))
    return power

# ==============================================================
# --- ФОНОВЫЕ ПОТОКИ ---
# ==============================================================
def market_price_updater():
    while True:
        time.sleep(3600)
        assets = db_query("SELECT name, price, base_price FROM market_assets")
        for name, price, base_price in assets:
            change = random.uniform(-0.25, 0.25)
            new_price = price * (1 + change)
            new_price = max(base_price * 0.5, min(base_price * 2.0, new_price))
            new_price = round(new_price, 2)
            db_query("UPDATE market_assets SET price = ?, last_updated = ? WHERE name = ?",
                     (new_price, time.time(), name))

def passive_income_distributor():
    INTERVAL = 600
    while True:
        time.sleep(INTERVAL)
        owners = db_query('''
            SELECT ub.user_id, ub.quantity, bt.income_per_hour
            FROM user_businesses ub
            JOIN business_types bt ON ub.business_name = bt.name
        ''')
        income_map = {}
        for user_id, qty, iph in owners:
            income = int(iph * qty * (INTERVAL / 3600))
            income_map[user_id] = income_map.get(user_id, 0) + income
        for user_id, income in income_map.items():
            if income > 0:
                db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (income, user_id))

def ep_generator():
    """Генерирует ОЭ каждые 12 часов для владельцев заводов и шахт."""
    EP_INTERVAL = 43200
    while True:
        time.sleep(600)
        current_time = time.time()
        # Собираем ОЭ-потенциал каждого игрока
        owners = db_query('''
            SELECT ub.user_id, ub.quantity, bt.ep_per_12h
            FROM user_businesses ub
            JOIN business_types bt ON ub.business_name = bt.name
            WHERE bt.ep_per_12h > 0
        ''')
        ep_map = {}
        for user_id, qty, ep12 in owners:
            ep_map[user_id] = ep_map.get(user_id, 0) + ep12 * qty

        users_ep_data = db_query("SELECT user_id, last_ep FROM users")
        for user_id, last_ep in (users_ep_data or []):
            if user_id in ep_map:
                last_ep = last_ep or 0
                if (current_time - last_ep) >= EP_INTERVAL:
                    industry_level = get_user_tech_level(user_id, 'industry')
                    bonus = 1 + industry_level * 0.20
                    ep_gain = int(ep_map[user_id] * bonus)
                    if ep_gain > 0:
                        db_query("UPDATE users SET ep = ep + ?, last_ep = ? WHERE user_id = ?",
                                 (ep_gain, current_time, user_id))

def army_maintenance():
    """Каждый час: снимает деньги за содержание пехоты.
       Каждые 3 часа: снимает нефть за танки."""
    oil_accumulator = {}
    tick = 0
    while True:
        time.sleep(3600)
        tick += 1

        # Содержание пехоты: каждые 5 солдат = 1 💰/час
        users = db_query("SELECT user_id, troops FROM users WHERE troops > 0 AND banned = 0")
        for user_id, troops in (users or []):
            logistics_level = get_user_tech_level(user_id, 'logistics')
            reduction = max(0.1, 1 - logistics_level * 0.10)
            maintenance = int((troops / 5) * reduction)
            if maintenance > 0:
                db_query("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?",
                         (maintenance, user_id))

        # Расход нефти танками каждые 3 часа
        if tick % 3 == 0:
            tank_owners = db_query('''
                SELECT user_id, quantity FROM user_military
                WHERE unit_name = 'tank' AND quantity > 0
            ''')
            for user_id, tank_count in (tank_owners or []):
                energy_level = get_user_tech_level(user_id, 'energy')
                energy_red = max(0.1, 1 - energy_level * 0.10)
                oil_needed = get_tank_oil_consumption(tank_count) * energy_red

                oil_accumulator[user_id] = oil_accumulator.get(user_id, 0.0) + oil_needed
                to_deduct = int(oil_accumulator[user_id])
                if to_deduct > 0:
                    oil_accumulator[user_id] -= to_deduct
                    current_oil = db_query(
                        "SELECT quantity FROM user_portfolio WHERE user_id = ? AND asset_name = 'oil'",
                        (user_id,), fetchone=True
                    )
                    if current_oil:
                        actual_deduct = min(to_deduct, int(current_oil[0]))
                        if actual_deduct > 0:
                            db_query(
                                "UPDATE user_portfolio SET quantity = quantity - ? WHERE user_id = ? AND asset_name = 'oil'",
                                (actual_deduct, user_id)
                            )

threading.Thread(target=market_price_updater, daemon=True).start()
threading.Thread(target=passive_income_distributor, daemon=True).start()
threading.Thread(target=ep_generator, daemon=True).start()
threading.Thread(target=army_maintenance, daemon=True).start()

# ==============================================================
# --- ОСНОВНЫЕ КОМАНДЫ ---
# ==============================================================

@bot.message_handler(commands=['start'])
@group_only
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"player_{user_id}"

    if is_banned(user_id):
        return bot.reply_to(message, "⛔ Вы заблокированы в Аурелии.")

    user = db_query("SELECT * FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user:
        db_query("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        bot.reply_to(message,
            "🌍 *Добро пожаловать в мир Аурелии!*\n\n"
            "💰 Стартовый капитал: 1000\n\n"
            "📋 *Основные команды:*\n"
            "/profile — профиль\n"
            "/cash — сбор налогов (каждые 30 мин)\n"
            "/upgrade — улучшить экономику\n"
            "/pay @юзер сумма — перевод денег\n"
            "/senditem @юзер актив кол-во — передача ресурсов\n\n"
            "🏢 *Бизнес и Биржа:*\n"
            "/shop | /buybiz | /mybiz\n"
            "/market | /buy | /sell | /portfolio\n\n"
            "⚔️ *Армия и Флот:*\n"
            "/draft — призыв войск (раз в 2 ч)\n"
            "/craft — производство техники\n"
            "/army — просмотр армии\n\n"
            "🛢️ *Нефтедобыча:*\n"
            "/extractoil — добыть нефть (нужна нефтекачка)\n\n"
            "🔬 *Технологии:*\n"
            "/tech — дерево технологий\n"
            "/researchtech [тех] — исследовать\n\n"
            "🏆 *Рейтинги:*\n"
            "/top — рейтинги ресурсов\n"
            "/toparmy — военная мощь\n"
            "/worldstats — мировая статистика",
            parse_mode="Markdown"
        )
    else:
        db_query("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        bot.reply_to(message, "Вы уже зарегистрированы в Аурелии! Используйте /profile.")

@bot.message_handler(commands=['profile'])
@group_only
def profile_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    username = message.from_user.username or f"player_{user_id}"
    db_query("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))

    user = db_query("SELECT balance, level, troops, ep FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user:
        return bot.reply_to(message, "Вы не зарегистрированы! Введите /start.")

    biz_data = db_query('''
        SELECT ub.quantity, bt.income_per_hour FROM user_businesses ub
        JOIN business_types bt ON ub.business_name = bt.name
        WHERE ub.user_id = ?
    ''', (user_id,))
    passive = sum(q * iph for q, iph in biz_data) if biz_data else 0

    extractor = db_query("SELECT quantity FROM user_extractors WHERE user_id = ?", (user_id,), fetchone=True)
    ext_qty = extractor[0] if extractor else 0

    mil_power = calc_military_power(user_id)

    bot.reply_to(message,
        f"👤 *Профиль @{username}:*\n\n"
        f"💰 Баланс: {user[0]}\n"
        f"📈 Уровень экономики: {user[1]}\n"
        f"🪖 Пехота в резерве: {user[2]}\n"
        f"⚔️ Военная мощь: {mil_power}\n"
        f"🏭 Пассивный доход: ~{passive} 💰/час\n"
        f"🔬 Очки экономики (ОЭ): {user[3]}\n"
        f"🛢️ Нефтекачек: {ext_qty}\n\n"
        f"Используйте /cash для сбора налогов.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['cash'])
@group_only
def cash_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    user = db_query("SELECT balance, level, last_cash FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user:
        return bot.reply_to(message, "Сначала введите /start")

    balance, level, last_cash = user
    current_time = time.time()
    cooldown = 1800

    if current_time - last_cash < cooldown:
        left_time = int(cooldown - (current_time - last_cash))
        bot.reply_to(message, f"⏳ Казна пуста. Следующий сбор через {left_time // 60} мин. {left_time % 60} сек.")
        return

    base_income = 500
    level_multiplier = 1 + (level * 0.2)
    finance_bonus = 1 + get_user_tech_level(user_id, 'finance') * 0.10
    market_luck = random.uniform(0.8, 1.2)
    earned = int(base_income * level_multiplier * finance_bonus * market_luck)
    new_balance = balance + earned

    db_query("UPDATE users SET balance = ?, last_cash = ? WHERE user_id = ?", (new_balance, current_time, user_id))
    bot.reply_to(message, f"💵 Вы собрали налоги: *{earned}* 💰\nБаланс: {new_balance} 💰", parse_mode="Markdown")

@bot.message_handler(commands=['upgrade'])
@group_only
def upgrade_command(message):
    if is_banned(message.from_user.id): return
    user = db_query("SELECT balance, level FROM users WHERE user_id = ?", (message.from_user.id,), fetchone=True)
    if not user:
        return bot.reply_to(message, "Введите /start")
    balance, level = user
    upgrade_cost = level * 3000  # удвоено
    if balance >= upgrade_cost:
        db_query("UPDATE users SET balance = ?, level = ? WHERE user_id = ?",
                 (balance - upgrade_cost, level + 1, message.from_user.id))
        bot.reply_to(message, f"✅ Экономика улучшена до {level + 1} уровня за {upgrade_cost} 💰!")
    else:
        bot.reply_to(message, f"❌ Недостаточно средств.\nНужно: {upgrade_cost} 💰\nБаланс: {balance} 💰")

# ==============================================================
# --- НЕФТЕДОБЫЧА ---
# ==============================================================

@bot.message_handler(commands=['extractoil'])
@group_only
def extractoil_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return

    extractor = db_query("SELECT quantity, last_extract FROM user_extractors WHERE user_id = ?",
                         (user_id,), fetchone=True)
    if not extractor or extractor[0] <= 0:
        return bot.reply_to(message,
            "❌ У вас нет нефтекачек.\n"
            "🛢️ Обратитесь к администрации для получения права на добычу нефти."
        )

    qty, last_extract = extractor
    current_time = time.time()
    cooldown = 3600

    if current_time - (last_extract or 0) < cooldown:
        left_time = int(cooldown - (current_time - last_extract))
        return bot.reply_to(message,
            f"⏳ Нефтекачки работают. Следующая добыча через {left_time // 60} мин. {left_time % 60} сек."
        )

    oil_gained = qty  # 1 нефть на качку в час
    db_query("UPDATE user_extractors SET last_extract = ? WHERE user_id = ?", (current_time, user_id))

    existing = db_query("SELECT quantity FROM user_portfolio WHERE user_id = ? AND asset_name = 'oil'",
                        (user_id,), fetchone=True)
    if existing:
        db_query("UPDATE user_portfolio SET quantity = quantity + ? WHERE user_id = ? AND asset_name = 'oil'",
                 (oil_gained, user_id))
    else:
        db_query("INSERT INTO user_portfolio (user_id, asset_name, quantity, avg_buy_price) VALUES (?,?,?,?)",
                 (user_id, 'oil', oil_gained, 0))

    total_oil = db_query("SELECT quantity FROM user_portfolio WHERE user_id = ? AND asset_name = 'oil'",
                         (user_id,), fetchone=True)
    bot.reply_to(message,
        f"🛢️ *Добыча нефти завершена!*\n"
        f"Добыто: *{oil_gained}* 🛢️ Нефти (по 1 на качку)\n"
        f"Итого нефти: {total_oil[0] if total_oil else oil_gained:.1f}",
        parse_mode="Markdown"
    )

# ==============================================================
# --- ТЕХНОЛОГИИ ---
# ==============================================================

@bot.message_handler(commands=['tech'])
@group_only
def tech_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return

    techs = db_query("SELECT name, display_name, max_level, ep_cost_per_level, description FROM tech_types")
    user_ep = db_query("SELECT ep FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    ep = user_ep[0] if user_ep else 0

    text = f"🔬 *Дерево технологий Аурелии*\n💡 Ваши ОЭ: {ep}\n\n"
    for name, display, max_lv, ep_cost, desc in techs:
        current_lv = get_user_tech_level(user_id, name)
        if current_lv >= max_lv:
            status = "✅ МАКСИМУМ"
        else:
            status = f"Ур. {current_lv}/{max_lv} | Цена: {ep_cost} ОЭ"
        text += f"*{display}* (`{name}`)\n  _{desc}_\n  {status}\n\n"

    text += "Исследовать: `/researchtech [название]`"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['researchtech'])
@group_only
def researchtech_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return

    args = message.text.split()
    if len(args) < 2:
        return bot.reply_to(message, "Использование: /researchtech [название]\nСписок: /tech")

    tech_name = args[1].lower()
    tech = db_query("SELECT display_name, max_level, ep_cost_per_level FROM tech_types WHERE name = ?",
                    (tech_name,), fetchone=True)
    if not tech:
        return bot.reply_to(message, f"❌ Технология '{tech_name}' не найдена. Смотри /tech")

    display, max_lv, ep_cost = tech
    current_lv = get_user_tech_level(user_id, tech_name)

    if current_lv >= max_lv:
        return bot.reply_to(message,
            f"✅ Технология *{display}* уже на максимальном уровне ({max_lv}).",
            parse_mode="Markdown"
        )

    user_ep = db_query("SELECT ep FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    ep = user_ep[0] if user_ep else 0

    if ep < ep_cost:
        return bot.reply_to(message,
            f"❌ Недостаточно ОЭ.\n"
            f"Нужно: {ep_cost} ОЭ\nУ вас: {ep} ОЭ\n\n"
            f"💡 Получайте ОЭ через заводы и шахты (/shop)"
        )

    db_query("UPDATE users SET ep = ep - ? WHERE user_id = ?", (ep_cost, user_id))
    if current_lv == 0:
        db_query("INSERT INTO user_tech (user_id, tech_name, level) VALUES (?, ?, 1)", (user_id, tech_name))
    else:
        db_query("UPDATE user_tech SET level = level + 1 WHERE user_id = ? AND tech_name = ?",
                 (user_id, tech_name))

    new_lv = current_lv + 1
    bot.reply_to(message,
        f"🔬 *Технология исследована!*\n"
        f"{display} → Уровень *{new_lv}/{max_lv}*\n"
        f"Потрачено: {ep_cost} ОЭ",
        parse_mode="Markdown"
    )

# ==============================================================
# --- ВОЕННОЕ ДЕЛО И ПРОИЗВОДСТВО ---
# ==============================================================

GROUND_UNITS = {'rifle', 'tank', 'artillery', 'aa_gun'}
AIR_UNITS    = {'plane', 'bomber', 'bomb'}
NAVY_UNITS   = {'ship', 'submarine', 'carrier'}

@bot.message_handler(commands=['draft'])
@group_only
def draft_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    user = db_query("SELECT troops, last_draft FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user:
        return bot.reply_to(message, "Сначала введите /start")

    troops, last_draft = user
    current_time = time.time()
    cooldown = 7200

    if current_time - (last_draft or 0) < cooldown:
        left_time = int(cooldown - (current_time - last_draft))
        bot.reply_to(message,
            f"⏳ Резервы истощены. Следующий призыв через "
            f"{left_time // 3600} ч. {(left_time % 3600) // 60} мин."
        )
        return

    new_recruits = random.randint(1000, 2000)
    db_query("UPDATE users SET troops = troops + ?, last_draft = ? WHERE user_id = ?",
             (new_recruits, current_time, user_id))
    bot.reply_to(message,
        f"🪖 *Призыв завершен!*\n"
        f"В ряды армии вступило *{new_recruits}* новобранцев.\n"
        f"Всего пехоты: {troops + new_recruits}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['craft'])
@group_only
def craft_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    args = message.text.split()
    if len(args) < 3:
        types = db_query("SELECT name, display_name, steel_cost, money_cost FROM military_types")
        text = "⚙️ *Военное и морское производство:*\nИспользование: `/craft [тип] [количество]`\n\n"
        text += "🪖 *Наземные силы:*\n"
        for name, display, steel, money in types:
            if name in GROUND_UNITS:
                text += f"  {display} (`{name}`) — {steel} ⚙️ Стали, {money} 💰\n"
        text += "\n✈️ *Авиация:*\n"
        for name, display, steel, money in types:
            if name in AIR_UNITS:
                text += f"  {display} (`{name}`) — {steel} ⚙️ Стали, {money} 💰\n"
        text += "\n🚢 *Военно-морской флот:*\n"
        for name, display, steel, money in types:
            if name in NAVY_UNITS:
                text += f"  {display} (`{name}`) — {steel} ⚙️ Стали, {money} 💰\n"
        return bot.reply_to(message, text, parse_mode="Markdown")

    unit_name = args[1].lower()
    try:
        qty = int(args[2])
    except ValueError:
        return bot.reply_to(message, "Количество должно быть числом.")
    if qty <= 0:
        return bot.reply_to(message, "Количество должно быть больше нуля.")

    unit = db_query("SELECT display_name, steel_cost, money_cost FROM military_types WHERE name = ?",
                    (unit_name,), fetchone=True)
    if not unit:
        return bot.reply_to(message, f"❌ Чертеж '{unit_name}' не найден.")

    display, steel_cost, money_cost = unit

    # Применяем бонусы технологий
    met_level = get_user_tech_level(user_id, 'metallurgy')
    eng_level = get_user_tech_level(user_id, 'engineering')
    steel_mult = max(0.2, 1 - met_level * 0.08)
    money_mult = max(0.2, 1 - eng_level * 0.08)

    total_steel = int(steel_cost * qty * steel_mult)
    total_money = int(money_cost * qty * money_mult)

    user = db_query("SELECT balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    user_steel = db_query(
        "SELECT quantity FROM user_portfolio WHERE user_id = ? AND asset_name = 'steel'",
        (user_id,), fetchone=True
    )

    current_steel = int(user_steel[0]) if user_steel else 0
    current_money = user[0] if user else 0

    if current_money < total_money or current_steel < total_steel:
        return bot.reply_to(message,
            f"❌ Недостаточно ресурсов!\n"
            f"Требуется: {total_steel} ⚙️ Стали и {total_money} 💰\n"
            f"В наличии: {current_steel} ⚙️ Стали и {current_money} 💰"
        )

    db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_money, user_id))
    db_query("UPDATE user_portfolio SET quantity = quantity - ? WHERE user_id = ? AND asset_name = 'steel'",
             (total_steel, user_id))
    db_query('''
        INSERT INTO user_military (user_id, unit_name, quantity)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, unit_name) DO UPDATE SET quantity = quantity + ?
    ''', (user_id, unit_name, qty, qty))

    bot.reply_to(message,
        f"🏭 Произведено: *{qty}x {display}*\n"
        f"Потрачено: {total_steel} ⚙️ Стали, {total_money} 💰",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['army'])
@group_only
def army_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    user = db_query("SELECT troops FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user:
        return bot.reply_to(message, "Сначала введите /start")

    units_raw = db_query('''
        SELECT u.unit_name, m.display_name, u.quantity
        FROM user_military u
        JOIN military_types m ON u.unit_name = m.name
        WHERE u.user_id = ? AND u.quantity > 0
    ''', (user_id,))

    ground_lines, air_lines, navy_lines = [], [], []
    for unit_name, display, qty in (units_raw or []):
        line = f"  {display}: {qty} шт."
        if unit_name in GROUND_UNITS:
            ground_lines.append(line)
        elif unit_name in AIR_UNITS:
            air_lines.append(line)
        elif unit_name in NAVY_UNITS:
            navy_lines.append(line)

    logistics_level = get_user_tech_level(user_id, 'logistics')
    reduction = max(0.1, 1 - logistics_level * 0.10)
    hourly_cost = int((user[0] / 5) * reduction)

    tank_data = db_query("SELECT quantity FROM user_military WHERE user_id = ? AND unit_name = 'tank'",
                         (user_id,), fetchone=True)
    tank_count = tank_data[0] if tank_data else 0
    energy_level = get_user_tech_level(user_id, 'energy')
    energy_red = max(0.1, 1 - energy_level * 0.10)
    oil_per_3h = round(get_tank_oil_consumption(tank_count) * energy_red, 2)

    mil_power = calc_military_power(user_id)

    text = "⚔️ *Вооруженные силы Аурелии:*\n\n"
    text += f"🪖 *Наземные силы:*\n  Пехота: {user[0]}\n"
    text += ("\n".join(ground_lines) + "\n") if ground_lines else "  Техника отсутствует\n"
    text += "\n✈️ *Авиация:*\n"
    text += ("\n".join(air_lines) + "\n") if air_lines else "  Авиация отсутствует\n"
    text += "\n🚢 *Военно-морской флот:*\n"
    text += ("\n".join(navy_lines) + "\n") if navy_lines else "  Флот отсутствует\n"
    text += f"\n⚔️ *Общая военная мощь: {mil_power}*\n"
    text += f"💸 Содержание пехоты: ~{hourly_cost} 💰/час\n"
    text += f"🛢️ Расход нефти танками: {oil_per_3h} / 3 часа\n"
    text += "\n💡 Производство техники: /craft"

    bot.reply_to(message, text, parse_mode="Markdown")

# ==============================================================
# --- РЕЙТИНГИ И СТАТИСТИКА ---
# ==============================================================

@bot.message_handler(commands=['toparmy'])
@group_only
def toparmy_command(message):
    users = db_query("SELECT user_id, username FROM users WHERE banned = 0")
    powers = []
    for user_id, username in (users or []):
        power = calc_military_power(user_id)
        if power > 0:
            powers.append((username, power))
    powers.sort(key=lambda x: x[1], reverse=True)
    powers = powers[:10]

    if not powers:
        return bot.reply_to(message, "Рейтинг пуст.")

    text = "⚔️ *Рейтинг военной мощи Аурелии:*\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (uname, power) in enumerate(powers, 1):
        prefix = medals[i-1] if i <= 3 else f"{i}."
        text += f"{prefix} @{uname} — {power} ⚔️\n"
    text += "\n💡 Мощь = (пехота × 1) + (техника × коэффициент) × бонус технологий"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['top'])
@group_only
def top_command(message):
    args = message.text.split()
    if len(args) < 2:
        assets = db_query("SELECT name, display_name FROM market_assets")
        text = "🏆 *Рейтинги мира Аурелия:*\n\nИспользование: `/top [категория]`\n\n"
        text += "`/top money` — Топ по валюте 💰\n"
        text += "`/top ep` — Топ по ОЭ 🔬\n"
        for name, display in assets:
            text += f"`/top {name}` — Топ по {display}\n"
        text += "\n⚔️ Военный рейтинг: /toparmy"
        return bot.reply_to(message, text, parse_mode="Markdown")

    category = args[1].lower()

    if category == 'money':
        top_users = db_query(
            "SELECT username, balance FROM users WHERE balance > 0 AND banned = 0 ORDER BY balance DESC LIMIT 10"
        )
        if not top_users:
            return bot.reply_to(message, "Рейтинг пуст.")
        text = "🏆 *Топ богатейших правителей (Баланс):*\n\n"
        for i, (uname, val) in enumerate(top_users, start=1):
            text += f"{i}. @{uname} — {val} 💰\n"
        return bot.reply_to(message, text, parse_mode="Markdown")

    if category == 'ep':
        top_users = db_query(
            "SELECT username, ep FROM users WHERE ep > 0 AND banned = 0 ORDER BY ep DESC LIMIT 10"
        )
        if not top_users:
            return bot.reply_to(message, "Рейтинг пуст.")
        text = "🏆 *Топ по Очкам Экономики (ОЭ):*\n\n"
        for i, (uname, val) in enumerate(top_users, start=1):
            text += f"{i}. @{uname} — {val} ОЭ 🔬\n"
        return bot.reply_to(message, text, parse_mode="Markdown")

    asset = db_query("SELECT display_name FROM market_assets WHERE name = ?", (category,), fetchone=True)
    if not asset:
        return bot.reply_to(message, f"❌ Категория '{category}' не найдена. Напишите `/top` для списка.")

    display = asset[0]
    top_users = db_query('''
        SELECT u.username, p.quantity
        FROM user_portfolio p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.asset_name = ? AND p.quantity > 0 AND u.banned = 0
        ORDER BY p.quantity DESC LIMIT 10
    ''', (category,))

    if not top_users:
        return bot.reply_to(message, f"Рейтинг по активу {display} пока пуст.")

    text = f"🏆 *Топ магнатов Аурелии ({display}):*\n\n"
    for i, (uname, val) in enumerate(top_users, start=1):
        text += f"{i}. @{uname} — {val:.1f} шт.\n"
    return bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['worldstats'])
@group_only
def worldstats_command(message):
    total_money = db_query("SELECT SUM(balance) FROM users WHERE banned = 0", fetchone=True)[0] or 0
    total_troops = db_query("SELECT SUM(troops) FROM users WHERE banned = 0", fetchone=True)[0] or 0
    total_users = db_query("SELECT COUNT(*) FROM users WHERE banned = 0", fetchone=True)[0] or 0
    total_ep = db_query("SELECT SUM(ep) FROM users WHERE banned = 0", fetchone=True)[0] or 0
    total_oil = db_query("SELECT SUM(quantity) FROM user_portfolio WHERE asset_name = 'oil'",
                         fetchone=True)[0] or 0

    bot.reply_to(message,
        f"🌍 *Глобальная статистика мира Аурелия:*\n\n"
        f"👥 Зарегистрировано правителей: {total_users}\n"
        f"💰 Валюты в обороте: {total_money} 💰\n"
        f"🪖 Общая численность мировых войск: {total_troops}\n"
        f"🔬 Очков экономики в мире: {total_ep} ОЭ\n"
        f"🛢️ Нефти в мире: {total_oil:.1f}",
        parse_mode="Markdown"
    )

# ==============================================================
# --- ТОРГОВЛЯ И ПЕРЕВОДЫ ---
# ==============================================================

@bot.message_handler(commands=['pay'])
@group_only
def pay_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    args = message.text.split()
    if len(args) != 3:
        return bot.reply_to(message, "Использование: /pay @юзернейм [сумма]")

    target_username = args[1].lstrip('@').lower()
    try:
        amount = int(args[2])
    except ValueError:
        return bot.reply_to(message, "Сумма должна быть числом.")
    if amount <= 0:
        return bot.reply_to(message, "Сумма должна быть больше нуля.")

    sender_username = (message.from_user.username or "").lower()
    if target_username == sender_username:
        return bot.reply_to(message, "Нельзя переводить самому себе.")

    sender = db_query("SELECT balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    target = db_query("SELECT user_id, username FROM users WHERE LOWER(username) = ?",
                      (target_username,), fetchone=True)

    if not target:
        return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    if not sender or sender[0] < amount:
        return bot.reply_to(message, "❌ Недостаточно средств.")

    db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target[0]))
    bot.reply_to(message, f"💸 Переведено *{amount}* 💰 игроку @{target_username}.", parse_mode="Markdown")

@bot.message_handler(commands=['senditem'])
@group_only
def senditem_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    args = message.text.split()
    if len(args) != 4:
        return bot.reply_to(message,
            "Использование: `/senditem @юзернейм [актив] [количество]`\nНапример: `/senditem @ivan steel 10`",
            parse_mode="Markdown"
        )

    target_username = args[1].lstrip('@').lower()
    asset_name = args[2].lower()
    try:
        amount = int(args[3])
    except ValueError:
        return bot.reply_to(message, "Количество должно быть числом.")
    if amount <= 0:
        return bot.reply_to(message, "Количество должно быть больше нуля.")

    if target_username == (message.from_user.username or "").lower():
        return bot.reply_to(message, "Нельзя отправить ресурсы самому себе.")

    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target:
        return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    target_id = target[0]

    asset_check = db_query("SELECT display_name FROM market_assets WHERE name = ?", (asset_name,), fetchone=True)
    if not asset_check:
        return bot.reply_to(message, f"❌ Актив '{asset_name}' не существует.")
    display = asset_check[0]

    sender_portfolio = db_query(
        "SELECT quantity, avg_buy_price FROM user_portfolio WHERE user_id = ? AND asset_name = ?",
        (user_id, asset_name), fetchone=True
    )
    if not sender_portfolio or sender_portfolio[0] < amount:
        return bot.reply_to(message, f"❌ У вас недостаточно актива *{display}*.", parse_mode="Markdown")

    new_sender_qty = sender_portfolio[0] - amount
    if new_sender_qty <= 0:
        db_query("DELETE FROM user_portfolio WHERE user_id = ? AND asset_name = ?", (user_id, asset_name))
    else:
        db_query("UPDATE user_portfolio SET quantity = ? WHERE user_id = ? AND asset_name = ?",
                 (new_sender_qty, user_id, asset_name))

    target_portfolio = db_query(
        "SELECT quantity, avg_buy_price FROM user_portfolio WHERE user_id = ? AND asset_name = ?",
        (target_id, asset_name), fetchone=True
    )
    if target_portfolio:
        new_avg = ((target_portfolio[0] * target_portfolio[1]) + (amount * sender_portfolio[1])) / (target_portfolio[0] + amount)
        db_query(
            "UPDATE user_portfolio SET quantity = quantity + ?, avg_buy_price = ? WHERE user_id = ? AND asset_name = ?",
            (amount, new_avg, target_id, asset_name)
        )
    else:
        db_query(
            "INSERT INTO user_portfolio (user_id, asset_name, quantity, avg_buy_price) VALUES (?,?,?,?)",
            (target_id, asset_name, amount, sender_portfolio[1])
        )

    bot.reply_to(message,
        f"📦 Вы успешно передали *{amount}x {display}* игроку @{target_username}.\n"
        f"💡 Используйте вместе с /pay для безопасной торговли.",
        parse_mode="Markdown"
    )

# ==============================================================
# --- МАГАЗИН И БИЗНЕСЫ ---
# ==============================================================

@bot.message_handler(commands=['shop'])
@group_only
def shop_command(message):
    if is_banned(message.from_user.id): return
    businesses = db_query("SELECT name, display_name, cost, income_per_hour, description, ep_per_12h FROM business_types")
    text = "🏪 *Магазин бизнесов Аурелии:*\n\n"
    for name, display, cost, iph, desc, ep12 in businesses:
        ep_str = f"\n   🔬 ОЭ: +{ep12}/12 часов" if ep12 > 0 else ""
        text += (
            f"{display}\n"
            f"   💵 Цена: {cost} 💰\n"
            f"   📊 Доход: ~{iph} 💰/час{ep_str}\n"
            f"   📝 {desc}\n"
            f"   Купить: `/buybiz {name}`\n\n"
        )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['buybiz'])
@group_only
def buybiz_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    args = message.text.split()
    if len(args) < 2:
        return bot.reply_to(message, "Использование: /buybiz [название] [кол-во]\nСписок: /shop")

    biz_name = args[1].lower()
    qty = int(args[2]) if len(args) >= 3 and args[2].isdigit() else 1
    if qty < 1:
        return bot.reply_to(message, "Количество должно быть >= 1.")

    biz = db_query("SELECT display_name, cost, income_per_hour, ep_per_12h FROM business_types WHERE name = ?",
                   (biz_name,), fetchone=True)
    if not biz:
        return bot.reply_to(message, f"❌ Бизнес '{biz_name}' не найден. Смотри /shop")

    display, cost, iph, ep12 = biz
    total_cost = cost * qty
    user = db_query("SELECT balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user:
        return bot.reply_to(message, "Введите /start")
    if user[0] < total_cost:
        return bot.reply_to(message, f"❌ Недостаточно средств.\nНужно: {total_cost} 💰\nБаланс: {user[0]} 💰")

    db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, user_id))
    db_query('''
        INSERT INTO user_businesses (user_id, business_name, quantity)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, business_name) DO UPDATE SET quantity = quantity + ?
    ''', (user_id, biz_name, qty, qty))

    ep_str = f"\n🔬 Будет генерировать: +{ep12 * qty} ОЭ / 12 часов" if ep12 > 0 else ""
    bot.reply_to(message,
        f"✅ Куплено *{qty}x {display}* за {total_cost} 💰!\n"
        f"📊 Пассивный доход: ~{iph * qty} 💰/час{ep_str}\n"
        f"💡 Доход начисляется автоматически каждые 10 минут.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['mybiz'])
@group_only
def mybiz_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    businesses = db_query('''
        SELECT bt.display_name, ub.quantity, bt.income_per_hour, bt.ep_per_12h
        FROM user_businesses ub
        JOIN business_types bt ON ub.business_name = bt.name
        WHERE ub.user_id = ?
    ''', (user_id,))

    if not businesses:
        return bot.reply_to(message, "У вас нет бизнесов. Купите их в /shop")

    text = "🏢 *Ваши бизнесы:*\n\n"
    total_iph = 0
    total_ep12 = 0
    for display, qty, iph, ep12 in businesses:
        subtotal = iph * qty
        ep_sub = ep12 * qty
        total_iph += subtotal
        total_ep12 += ep_sub
        ep_str = f" | +{ep_sub} ОЭ/12ч" if ep12 > 0 else ""
        text += f"{display} x{qty} — {subtotal} 💰/час{ep_str}\n"

    text += (
        f"\n📊 *Итого: ~{total_iph} 💰/час*\n"
        f"🔬 *ОЭ за 12 часов: +{total_ep12} ОЭ*\n"
        f"💰 В сутки: ~{total_iph * 24} 💰\n\n"
        f"💡 Доход начисляется каждые 10 минут автоматически."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

# ==============================================================
# --- БИРЖА ---
# ==============================================================

@bot.message_handler(commands=['market'])
@group_only
def market_command(message):
    if is_banned(message.from_user.id): return
    assets = db_query("SELECT name, display_name, price, base_price FROM market_assets")
    text = "📊 *Биржа Аурелии — Текущие цены:*\n\n"
    for name, display, price, base_price in assets:
        arrow = get_price_arrow(price, base_price)
        change_pct = ((price - base_price) / base_price) * 100
        sign = "+" if change_pct >= 0 else ""
        text += (
            f"{arrow} *{display}*\n"
            f"   💵 Цена: {price:.2f} 💰 ({sign}{change_pct:.1f}% от базовой)\n"
            f"   Купить: `/buy {name} [кол-во]`  Продать: `/sell {name} [кол-во]`\n\n"
        )
    text += "⏰ Цены обновляются каждый час.\n/portfolio — ваш портфель"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['buy'])
@group_only
def buy_asset_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    args = message.text.split()
    if len(args) < 3:
        return bot.reply_to(message, "Использование: /buy [актив] [количество]\nСписок активов: /market")

    asset_name = args[1].lower()
    try:
        qty = int(args[2])
    except ValueError:
        return bot.reply_to(message, "Количество должно быть числом.")
    if qty <= 0:
        return bot.reply_to(message, "Количество должно быть > 0.")

    asset = db_query("SELECT display_name, price FROM market_assets WHERE name = ?", (asset_name,), fetchone=True)
    if not asset:
        return bot.reply_to(message, f"❌ Актив '{asset_name}' не найден. Смотри /market")

    display, price = asset
    total_cost = round(price * qty, 2)

    user = db_query("SELECT balance FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user:
        return bot.reply_to(message, "Введите /start")
    if user[0] < total_cost:
        return bot.reply_to(message, f"❌ Недостаточно средств.\nНужно: {total_cost} 💰\nБаланс: {user[0]} 💰")

    existing = db_query(
        "SELECT quantity, avg_buy_price FROM user_portfolio WHERE user_id = ? AND asset_name = ?",
        (user_id, asset_name), fetchone=True
    )
    if existing:
        old_qty, old_avg = existing
        new_qty = old_qty + qty
        new_avg = ((old_avg * old_qty) + (price * qty)) / new_qty
        db_query(
            "UPDATE user_portfolio SET quantity = ?, avg_buy_price = ? WHERE user_id = ? AND asset_name = ?",
            (new_qty, new_avg, user_id, asset_name)
        )
    else:
        db_query(
            "INSERT INTO user_portfolio (user_id, asset_name, quantity, avg_buy_price) VALUES (?,?,?,?)",
            (user_id, asset_name, qty, price)
        )

    db_query("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, user_id))
    bot.reply_to(message,
        f"✅ Куплено: *{qty}x {display}* за {total_cost:.2f} 💰\n"
        f"📊 Цена покупки: {price:.2f} 💰\n"
        f"💡 Следите за ценами через /market",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['sell'])
@group_only
def sell_asset_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    args = message.text.split()
    if len(args) < 3:
        return bot.reply_to(message, "Использование: /sell [актив] [количество]\nВаш портфель: /portfolio")

    asset_name = args[1].lower()
    try:
        qty = int(args[2])
    except ValueError:
        return bot.reply_to(message, "Количество должно быть числом.")
    if qty <= 0:
        return bot.reply_to(message, "Количество должно быть > 0.")

    asset = db_query("SELECT display_name, price FROM market_assets WHERE name = ?", (asset_name,), fetchone=True)
    if not asset:
        return bot.reply_to(message, f"❌ Актив '{asset_name}' не найден.")

    display, price = asset
    holding = db_query(
        "SELECT quantity, avg_buy_price FROM user_portfolio WHERE user_id = ? AND asset_name = ?",
        (user_id, asset_name), fetchone=True
    )
    if not holding or holding[0] < qty:
        owned = holding[0] if holding else 0
        return bot.reply_to(message, f"❌ Недостаточно активов.\nУ вас: {owned:.1f} {display}")

    old_qty, avg_buy = holding
    total_revenue = round(price * qty, 2)
    profit = round((price - avg_buy) * qty, 2)
    profit_str = f"+{profit:.2f}" if profit >= 0 else f"{profit:.2f}"
    profit_emoji = "📈" if profit >= 0 else "📉"

    new_qty = old_qty - qty
    if new_qty <= 0:
        db_query("DELETE FROM user_portfolio WHERE user_id = ? AND asset_name = ?", (user_id, asset_name))
    else:
        db_query("UPDATE user_portfolio SET quantity = ? WHERE user_id = ? AND asset_name = ?",
                 (new_qty, user_id, asset_name))

    db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_revenue, user_id))
    bot.reply_to(message,
        f"💰 Продано: *{qty}x {display}* за {total_revenue:.2f} 💰\n"
        f"{profit_emoji} Прибыль/убыток: *{profit_str} 💰*\n"
        f"(Средняя цена покупки: {avg_buy:.2f} 💰)",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['portfolio'])
@group_only
def portfolio_command(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    holdings = db_query('''
        SELECT p.asset_name, p.quantity, p.avg_buy_price, m.price, m.display_name
        FROM user_portfolio p
        JOIN market_assets m ON p.asset_name = m.name
        WHERE p.user_id = ? AND p.quantity > 0
    ''', (user_id,))

    if not holdings:
        return bot.reply_to(message, "Ваш портфель пуст.\nНачните инвестировать через /market")

    text = "💼 *Ваш инвестиционный портфель:*\n\n"
    total_invested = 0
    total_current = 0

    for asset_name, qty, avg_buy, cur_price, display in holdings:
        invested = avg_buy * qty
        current = cur_price * qty
        profit = current - invested
        profit_str = f"+{profit:.2f}" if profit >= 0 else f"{profit:.2f}"
        arrow = "📈" if profit >= 0 else "📉"
        total_invested += invested
        total_current += current
        text += (
            f"{arrow} *{display}* x{qty:.1f}\n"
            f"   Куплено по: {avg_buy:.2f} — Сейчас: {cur_price:.2f}\n"
            f"   Стоимость: {current:.2f} 💰 (P&L: {profit_str} 💰)\n\n"
        )

    total_profit = total_current - total_invested
    total_str = f"+{total_profit:.2f}" if total_profit >= 0 else f"{total_profit:.2f}"
    text += (
        f"📊 *Вложено: {total_invested:.2f} 💰*\n"
        f"💰 *Текущая стоимость: {total_current:.2f} 💰*\n"
        f"{'📈' if total_profit >= 0 else '📉'} *Общий P&L: {total_str} 💰*"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

# ==============================================================
# --- ADMIN-КОМАНДЫ (23 штуки) ---
# ==============================================================

def admin_check(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Нет доступа.")
        return False
    return True

@bot.message_handler(commands=['setprice'])
@group_only
def setprice_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /setprice [актив] [цена]")
    asset_name = args[1].lower()
    try: new_price = float(args[2])
    except: return bot.reply_to(message, "Цена должна быть числом.")
    if new_price <= 0: return bot.reply_to(message, "Цена > 0.")
    asset = db_query("SELECT display_name FROM market_assets WHERE name = ?", (asset_name,), fetchone=True)
    if not asset: return bot.reply_to(message, f"Актив '{asset_name}' не найден.")
    db_query("UPDATE market_assets SET price = ?, last_updated = ? WHERE name = ?", (new_price, time.time(), asset_name))
    bot.reply_to(message, f"✅ [ADMIN] Цена на *{asset[0]}* → {new_price:.2f} 💰", parse_mode="Markdown")

@bot.message_handler(commands=['setbaseprice'])
@group_only
def setbaseprice_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /setbaseprice [актив] [цена]")
    asset_name = args[1].lower()
    try: new_base = float(args[2])
    except: return bot.reply_to(message, "Цена должна быть числом.")
    asset = db_query("SELECT display_name FROM market_assets WHERE name = ?", (asset_name,), fetchone=True)
    if not asset: return bot.reply_to(message, f"Актив '{asset_name}' не найден.")
    db_query("UPDATE market_assets SET base_price = ? WHERE name = ?", (new_base, asset_name))
    bot.reply_to(message, f"✅ [ADMIN] Базовая цена *{asset[0]}* → {new_base:.2f} 💰", parse_mode="Markdown")

@bot.message_handler(commands=['givemoney'])
@group_only
def givemoney_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /givemoney @юзернейм [сумма]")
    target_username = args[1].lstrip('@').lower()
    try: amount = int(args[2])
    except: return bot.reply_to(message, "Сумма должна быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    db_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target[0]))
    bot.reply_to(message, f"✅ [ADMIN] @{target_username} получил {amount} 💰")

@bot.message_handler(commands=['takemoney'])
@group_only
def takemoney_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /takemoney @юзернейм [сумма]")
    target_username = args[1].lstrip('@').lower()
    try: amount = int(args[2])
    except: return bot.reply_to(message, "Сумма должна быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    db_query("UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?", (amount, target[0]))
    bot.reply_to(message, f"✅ [ADMIN] У @{target_username} снято {amount} 💰")

@bot.message_handler(commands=['giveitem'])
@group_only
def giveitem_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 4: return bot.reply_to(message, "Использование: /giveitem @юзернейм [актив] [кол-во]")
    target_username = args[1].lstrip('@').lower()
    asset_name = args[2].lower()
    try: amount = int(args[3])
    except: return bot.reply_to(message, "Количество должно быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    asset = db_query("SELECT price FROM market_assets WHERE name = ?", (asset_name,), fetchone=True)
    if not asset: return bot.reply_to(message, f"❌ Актив '{asset_name}' не найден.")
    target_id = target[0]
    existing = db_query("SELECT quantity FROM user_portfolio WHERE user_id = ? AND asset_name = ?",
                        (target_id, asset_name), fetchone=True)
    if existing:
        db_query("UPDATE user_portfolio SET quantity = quantity + ? WHERE user_id = ? AND asset_name = ?",
                 (amount, target_id, asset_name))
    else:
        db_query("INSERT INTO user_portfolio (user_id, asset_name, quantity, avg_buy_price) VALUES (?,?,?,?)",
                 (target_id, asset_name, amount, 0))
    bot.reply_to(message, f"✅ [ADMIN] @{target_username} получил {amount}x {asset_name}")

@bot.message_handler(commands=['takeitem'])
@group_only
def takeitem_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 4: return bot.reply_to(message, "Использование: /takeitem @юзернейм [актив] [кол-во]")
    target_username = args[1].lstrip('@').lower()
    asset_name = args[2].lower()
    try: amount = int(args[3])
    except: return bot.reply_to(message, "Количество должно быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    db_query("UPDATE user_portfolio SET quantity = MAX(0, quantity - ?) WHERE user_id = ? AND asset_name = ?",
             (amount, target[0], asset_name))
    bot.reply_to(message, f"✅ [ADMIN] У @{target_username} снято {amount}x {asset_name}")

@bot.message_handler(commands=['giveep'])
@group_only
def giveep_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /giveep @юзернейм [кол-во ОЭ]")
    target_username = args[1].lstrip('@').lower()
    try: amount = int(args[2])
    except: return bot.reply_to(message, "Количество должно быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    db_query("UPDATE users SET ep = ep + ? WHERE user_id = ?", (amount, target[0]))
    bot.reply_to(message, f"✅ [ADMIN] @{target_username} получил {amount} ОЭ 🔬")

@bot.message_handler(commands=['giveextractor'])
@group_only
def giveextractor_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /giveextractor @юзернейм [кол-во]")
    target_username = args[1].lstrip('@').lower()
    try: amount = int(args[2])
    except: return bot.reply_to(message, "Количество должно быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    target_id = target[0]
    existing = db_query("SELECT quantity FROM user_extractors WHERE user_id = ?", (target_id,), fetchone=True)
    if existing:
        db_query("UPDATE user_extractors SET quantity = quantity + ? WHERE user_id = ?", (amount, target_id))
    else:
        db_query("INSERT INTO user_extractors (user_id, quantity) VALUES (?, ?)", (target_id, amount))
    bot.reply_to(message, f"✅ [ADMIN] @{target_username} получил {amount} нефтекачек 🛢️")

@bot.message_handler(commands=['takeextractor'])
@group_only
def takeextractor_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /takeextractor @юзернейм [кол-во]")
    target_username = args[1].lstrip('@').lower()
    try: amount = int(args[2])
    except: return bot.reply_to(message, "Количество должно быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    db_query("UPDATE user_extractors SET quantity = MAX(0, quantity - ?) WHERE user_id = ?",
             (amount, target[0]))
    bot.reply_to(message, f"✅ [ADMIN] У @{target_username} снято {amount} нефтекачек")

@bot.message_handler(commands=['banuser'])
@group_only
def banuser_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 2: return bot.reply_to(message, "Использование: /banuser @юзернейм")
    target_username = args[1].lstrip('@').lower()
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    db_query("UPDATE users SET banned = 1 WHERE user_id = ?", (target[0],))
    bot.reply_to(message, f"✅ [ADMIN] Игрок @{target_username} заблокирован в Аурелии. 🚫")

@bot.message_handler(commands=['unbanuser'])
@group_only
def unbanuser_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 2: return bot.reply_to(message, "Использование: /unbanuser @юзернейм")
    target_username = args[1].lstrip('@').lower()
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    db_query("UPDATE users SET banned = 0 WHERE user_id = ?", (target[0],))
    bot.reply_to(message, f"✅ [ADMIN] Игрок @{target_username} разблокирован. ✅")

@bot.message_handler(commands=['setlevel'])
@group_only
def setlevel_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /setlevel @юзернейм [уровень]")
    target_username = args[1].lstrip('@').lower()
    try: level = int(args[2])
    except: return bot.reply_to(message, "Уровень должен быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    db_query("UPDATE users SET level = ? WHERE user_id = ?", (level, target[0]))
    bot.reply_to(message, f"✅ [ADMIN] Уровень экономики @{target_username} = {level}")

@bot.message_handler(commands=['settroops'])
@group_only
def settroops_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /settroops @юзернейм [кол-во]")
    target_username = args[1].lstrip('@').lower()
    try: amount = int(args[2])
    except: return bot.reply_to(message, "Количество должно быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    db_query("UPDATE users SET troops = ? WHERE user_id = ?", (amount, target[0]))
    bot.reply_to(message, f"✅ [ADMIN] Войска @{target_username} установлены на {amount}")

@bot.message_handler(commands=['givemilitary'])
@group_only
def givemilitary_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 4: return bot.reply_to(message, "Использование: /givemilitary @юзернейм [тип] [кол-во]")
    target_username = args[1].lstrip('@').lower()
    unit_name = args[2].lower()
    try: amount = int(args[3])
    except: return bot.reply_to(message, "Количество должно быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    unit = db_query("SELECT display_name FROM military_types WHERE name = ?", (unit_name,), fetchone=True)
    if not unit: return bot.reply_to(message, f"❌ Тип '{unit_name}' не найден.")
    target_id = target[0]
    existing = db_query("SELECT quantity FROM user_military WHERE user_id = ? AND unit_name = ?",
                        (target_id, unit_name), fetchone=True)
    if existing:
        db_query("UPDATE user_military SET quantity = quantity + ? WHERE user_id = ? AND unit_name = ?",
                 (amount, target_id, unit_name))
    else:
        db_query("INSERT INTO user_military (user_id, unit_name, quantity) VALUES (?,?,?)",
                 (target_id, unit_name, amount))
    bot.reply_to(message, f"✅ [ADMIN] @{target_username} получил {amount}x {unit[0]}")

@bot.message_handler(commands=['settech'])
@group_only
def settech_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 4: return bot.reply_to(message, "Использование: /settech @юзернейм [тех] [уровень]")
    target_username = args[1].lstrip('@').lower()
    tech_name = args[2].lower()
    try: level = int(args[3])
    except: return bot.reply_to(message, "Уровень должен быть числом.")
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    tech = db_query("SELECT display_name, max_level FROM tech_types WHERE name = ?", (tech_name,), fetchone=True)
    if not tech: return bot.reply_to(message, f"❌ Технология '{tech_name}' не найдена.")
    level = max(0, min(level, tech[1]))
    target_id = target[0]
    existing = db_query("SELECT level FROM user_tech WHERE user_id = ? AND tech_name = ?",
                        (target_id, tech_name), fetchone=True)
    if existing:
        db_query("UPDATE user_tech SET level = ? WHERE user_id = ? AND tech_name = ?",
                 (level, target_id, tech_name))
    else:
        db_query("INSERT INTO user_tech (user_id, tech_name, level) VALUES (?,?,?)",
                 (target_id, tech_name, level))
    bot.reply_to(message, f"✅ [ADMIN] Технология {tech[0]} для @{target_username} → Ур. {level}")

@bot.message_handler(commands=['wipeuser'])
@group_only
def wipeuser_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 2: return bot.reply_to(message, "Использование: /wipeuser @юзернейм")
    target_username = args[1].lstrip('@').lower()
    target = db_query("SELECT user_id FROM users WHERE LOWER(username) = ?", (target_username,), fetchone=True)
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")
    target_id = target[0]
    db_query("UPDATE users SET balance=1000, level=1, troops=0, ep=0, last_cash=0, last_draft=0 WHERE user_id=?",
             (target_id,))
    db_query("DELETE FROM user_businesses WHERE user_id = ?", (target_id,))
    db_query("DELETE FROM user_portfolio WHERE user_id = ?", (target_id,))
    db_query("DELETE FROM user_military WHERE user_id = ?", (target_id,))
    db_query("DELETE FROM user_tech WHERE user_id = ?", (target_id,))
    db_query("DELETE FROM user_extractors WHERE user_id = ?", (target_id,))
    bot.reply_to(message, f"✅ [ADMIN] Игрок @{target_username} полностью сброшен до начальных значений.")

@bot.message_handler(commands=['playerinfo'])
@group_only
def playerinfo_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 2: return bot.reply_to(message, "Использование: /playerinfo @юзернейм")
    target_username = args[1].lstrip('@').lower()
    target = db_query(
        "SELECT user_id, username, balance, level, troops, ep, banned FROM users WHERE LOWER(username) = ?",
        (target_username,), fetchone=True
    )
    if not target: return bot.reply_to(message, f"❌ Игрок @{target_username} не найден.")

    user_id, username, balance, level, troops, ep, banned = target
    extractor = db_query("SELECT quantity FROM user_extractors WHERE user_id = ?", (user_id,), fetchone=True)
    ext_qty = extractor[0] if extractor else 0
    mil_power = calc_military_power(user_id)

    techs = db_query("SELECT tech_name, level FROM user_tech WHERE user_id = ? AND level > 0", (user_id,))
    tech_str = ", ".join(f"{t}: {l}" for t, l in techs) if techs else "нет"

    text = (
        f"📋 *[ADMIN] Информация об игроке @{username}:*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"💰 Баланс: {balance}\n"
        f"📈 Уровень экономики: {level}\n"
        f"🪖 Пехота: {troops}\n"
        f"⚔️ Военная мощь: {mil_power}\n"
        f"🔬 ОЭ: {ep}\n"
        f"🛢️ Нефтекачек: {ext_qty}\n"
        f"🔬 Технологии: {tech_str}\n"
        f"🚫 Забанен: {'Да ❌' if banned else 'Нет ✅'}"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['marketevent'])
@group_only
def marketevent_command(message):
    if not admin_check(message): return
    args = message.text.split()
    if len(args) != 3: return bot.reply_to(message, "Использование: /marketevent [актив] [+-%]")
    asset_name = args[1].lower()
    try: percent = float(args[2])
    except: return bot.reply_to(message, "Процент должен быть числом.")
    asset = db_query("SELECT display_name, price FROM market_assets WHERE name = ?", (asset_name,), fetchone=True)
    if not asset: return bot.reply_to(message, f"Актив '{asset_name}' не найден.")
    display, old_price = asset
    new_price = round(max(0.01, old_price * (1 + percent / 100)), 2)
    db_query("UPDATE market_assets SET price = ?, last_updated = ? WHERE name = ?",
             (new_price, time.time(), asset_name))
    direction = "выросла" if percent >= 0 else "упала"
    arrow = "📈" if percent >= 0 else "📉"
    bot.reply_to(message,
        f"⚡ [ADMIN] Рыночное событие в Аурелии!\n\n"
        f"{arrow} Цена на *{display}* {direction} на {abs(percent):.1f}%\n"
        f"{old_price:.2f} → *{new_price:.2f}* 💰",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['marketcrash'])
@group_only
def marketcrash_command(message):
    if not admin_check(message): return
    assets = db_query("SELECT name, display_name, price FROM market_assets")
    text = "🔴 *[ADMIN] ОБВАЛ РЫНКА АУРЕЛИИ!*\n\n"
    for name, display, price in assets:
        drop = random.uniform(0.20, 0.50)
        new_price = round(price * (1 - drop), 2)
        db_query("UPDATE market_assets SET price = ?, last_updated = ? WHERE name = ?",
                 (new_price, time.time(), name))
        text += f"📉 {display}: {price:.2f} → *{new_price:.2f}* (-{drop*100:.1f}%)\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['marketboom'])
@group_only
def marketboom_command(message):
    if not admin_check(message): return
    assets = db_query("SELECT name, display_name, price FROM market_assets")
    text = "🟢 *[ADMIN] БУМ НА РЫНКЕ АУРЕЛИИ!*\n\n"
    for name, display, price in assets:
        rise = random.uniform(0.20, 0.50)
        new_price = round(price * (1 + rise), 2)
        db_query("UPDATE market_assets SET price = ?, last_updated = ? WHERE name = ?",
                 (new_price, time.time(), name))
        text += f"📈 {display}: {price:.2f} → *{new_price:.2f}* (+{rise*100:.1f}%)\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['resetmarket'])
@group_only
def resetmarket_command(message):
    if not admin_check(message): return
    db_query("UPDATE market_assets SET price = base_price, last_updated = ?", (time.time(),))
    bot.reply_to(message, "✅ [ADMIN] Все цены сброшены к базовым значениям.")

@bot.message_handler(commands=['broadcast'])
@group_only
def broadcast_command(message):
    if not admin_check(message): return
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return bot.reply_to(message, "Использование: /broadcast [текст]")
    text = f"📢 *Объявление от Администрации Аурелии:*\n\n{args[1]}"
    for group_id in ALLOWED_GROUP_IDS:
        try:
            bot.send_message(group_id, text, parse_mode="Markdown")
        except Exception as e:
            print(f"Broadcast error to {group_id}: {e}")
    bot.reply_to(message, "✅ Объявление отправлено во все группы.")

@bot.message_handler(commands=['announcement'])
@group_only
def announcement_command(message):
    if not admin_check(message): return
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return bot.reply_to(message, "Использование: /announcement [текст]")
    text = f"🌍 *СОБЫТИЕ В АУРЕЛИИ:*\n\n{args[1]}"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['adminhelp'])
@group_only
def adminhelp_command(message):
    if not admin_check(message): return
    bot.reply_to(message,
        "🔧 *Админ-команды Аурелии (23 команды):*\n\n"
        "💰 *Финансы:*\n"
        "/givemoney @user [сумма] — выдать деньги\n"
        "/takemoney @user [сумма] — снять деньги\n"
        "/giveep @user [кол-во] — выдать ОЭ\n\n"
        "📦 *Ресурсы и предметы:*\n"
        "/giveitem @user [актив] [кол-во] — выдать ресурс\n"
        "/takeitem @user [актив] [кол-во] — снять ресурс\n"
        "/giveextractor @user [кол-во] — выдать нефтекачки\n"
        "/takeextractor @user [кол-во] — снять нефтекачки\n"
        "/givemilitary @user [тип] [кол-во] — выдать технику\n\n"
        "⚙️ *Настройки игрока:*\n"
        "/setlevel @user [ур] — установить уровень экономики\n"
        "/settroops @user [кол-во] — установить войска\n"
        "/settech @user [тех] [ур] — установить уровень технологии\n"
        "/banuser @user — заблокировать игрока\n"
        "/unbanuser @user — разблокировать игрока\n"
        "/wipeuser @user — полный сброс игрока\n"
        "/playerinfo @user — полная информация\n\n"
        "📊 *Рынок:*\n"
        "/setprice [актив] [цена] — установить цену\n"
        "/setbaseprice [актив] [цена] — изменить базовую цену\n"
        "/marketevent [актив] [%] — изменить цену актива на %\n"
        "/marketcrash — обвал всего рынка\n"
        "/marketboom — рост всего рынка\n"
        "/resetmarket — сброс цен к базовым\n\n"
        "📢 *Оповещения:*\n"
        "/broadcast [текст] — сообщение во все группы\n"
        "/announcement [текст] — событие в текущей группе\n\n"
        "*Активы:* oil, gold, steel, aur\n"
        "*Технологии:* finance, logistics, metallurgy, engineering, military\\_sc, industry, energy, espionage",
        parse_mode="Markdown"
    )

# ==============================================================
bot.polling(none_stop=True)

