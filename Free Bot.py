import urllib.request
import urllib.parse
import urllib.error
import json
import time
import sys
import os

# উইন্ডোজ টার্মিনালে বাংলা ও ইমোজি সাপোর্ট করানোর জন্য (UTF-8 এনকোডিং ফোর্স করা হলো)
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ----------------- কনফিগারেশন অংশ -----------------
API_TOKEN = '8906178880:AAFxVw7OcYiUO9F38VjGL6iotJNg5k8VamE'
ADMIN_ID = 8428347588

REQUIRED_REFERRALS = 5  # কয়টি রেফার লাগবে (এখানে যা দিবেন বোটেও অটোমেটিক তাই দেখাবে)

# ১ নম্বর প্রাইভেট চ্যানেলের আইডি
PRIVATE_CHAT_ID = -1003919658897  

CHANNELS = [
    {
        "name": "চ্যানেল ১ 📢", 
        "url": "https://t.me/+1hSHLJ2y2R43MGE1", 
        "type": "private_auto_approve", 
        "check": True
    },
    {
        "name": "চ্যানেল ২ 📢", 
        "url": "https://t.me/+jV2iYeuKmXhiNDBl", 
        "type": "no_check", 
        "check": False
    },
    {
        "name": "পাবলিক চ্যানেল 📢", 
        "url": "https://t.me/freehackbotupdate", 
        "type": "public", 
        "username": "@freehackbotupdate", 
        "check": True
    }
]
# --------------------------------------------------

BASE_URL = f"https://api.telegram.org/bot{API_TOKEN}/"
BOT_USERNAME = None

DB_FILE = "bot_data.json"

db = {}
admin_categories = {}
claimed_stats = {} 

def save_data():
    try:
        data_to_save = {
            "db": db,
            "admin_categories": admin_categories,
            "claimed_stats": claimed_stats
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Data save error: {e}")

def load_data():
    global db, admin_categories, claimed_stats
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                raw_db = loaded_data.get("db", {})
                db = {int(k): v for k, v in raw_db.items()}
                admin_categories = loaded_data.get("admin_categories", {})
                claimed_stats = loaded_data.get("claimed_stats", {})
            print("Database loaded successfully.")
        except Exception as e:
            print(f"Data load error: {e}")

def make_request(method, payload):
    url = BASE_URL + method
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        print(f"❌ Telegram API Error ({method}): {error_msg}")
        return None
    except Exception as e:
        print(f"❌ Network Error ({method}): {e}")
        return None

def send_message(chat_id, text, reply_markup=None):
    # পার্স মোড পরিবর্তন করে HTML করা হয়েছে ক্র্যাশ এড়াতে
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return make_request("sendMessage", payload)

def edit_message_text(chat_id, message_id, text, reply_markup=None):
    # পার্স মোড পরিবর্তন করে HTML করা হয়েছে ক্র্যাশ এড়াতে
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return make_request("editMessageText", payload)

def answer_callback_query(callback_query_id, text, show_alert=False):
    payload = {"callback_query_id": callback_query_id, "text": text, "show_alert": show_alert}
    return make_request("answerCallbackQuery", payload)

def get_chat_member(chat_id, user_id):
    payload = {"chat_id": chat_id, "user_id": user_id}
    res = make_request("getChatMember", payload)
    if res and res.get("ok"):
        return res["result"]
    return None

def init_user(user_id, first_name="User"):
    if user_id not in db:
        db[user_id] = {
            "name": first_name,
            "referred_by": None, 
            "is_verified": False, 
            "referral_count": 0,
            "items_claimed": []
        }
        save_data()

def is_user_joined_all(user_id):
    for ch in CHANNELS:
        if not ch["check"]:
            continue
        
        if ch["type"] == "public":
            member = get_chat_member(ch["username"], user_id)
            if not member or member.get("status") in ["left", "kicked"]:
                return False
                
        elif ch["type"] == "private_auto_approve":
            if PRIVATE_CHAT_ID is None:
                continue
            member = get_chat_member(PRIVATE_CHAT_ID, user_id)
            if not member or member.get("status") in ["left", "kicked"]:
                return False
    return True

def handle_join_request(join_request):
    chat_id = join_request["chat"]["id"]
    chat_title = join_request["chat"].get("title", "Private Channel")
    user_id = join_request["from"]["id"]
    
    print(f"\n[ID FINDER] Channel: '{chat_title}' -> ID: {chat_id}")
    
    payload = {"chat_id": chat_id, "user_id": user_id}
    make_request("approveChatJoinRequest", payload)

def send_main_page(chat_id, message_id, user_id):
    global BOT_USERNAME
    if not BOT_USERNAME:
        me = make_request("getMe", {})
        BOT_USERNAME = me["result"]["username"] if (me and me.get("ok")) else "bot"
        
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    current_refs = db[user_id]["referral_count"]
    
    # HTML ফরম্যাটে ডাইনামিক টেক্সট রেডি করা হয়েছে
    text = f"🎯 <b>পরবর্তী ধাপ (Next Page):</b>\n\n" \
           f"এখান থেকে জিনিস নেওয়ার জন্য আপনার কমপক্ষে <b>{REQUIRED_REFERRALS} টি রেফার</b> লাগবে।\n\n" \
           f"🔗 <b>আপনার ইউনিক রেফারেল লিংক:</b>\n<code>{ref_link}</code>\n\n" \
           f"📊 <b>আপনার মোট রেফার:</b> {current_refs} / {REQUIRED_REFERRALS} টি\n\n" \
           f"📢 <b>নিয়ম:</b> আপনার লিংকে ক্লিক করে কেউ যখন সব চ্যানেলে জয়েন করে 'Joined' বাটনে ক্লিক করবে, তখনই কেবল আপনার রেফারটি কাউন্ট হবে।"
    
    inline_keyboard = [
        [{"text": "🔓 ACCESS", "callback_data": "click_access"}],
        [{"text": "🔄 Refresh Count (রেফার চেক করুন)", "callback_data": "refresh_count"}]
    ]
    edit_message_text(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})

def handle_message(msg):
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    first_name = msg["from"].get("first_name", "User")
    text = msg.get("text", "")
    
    init_user(user_id, first_name)
    
    if user_id == ADMIN_ID:
        if text.startswith("/add "):
            try:
                parts = text[5:].split("|", 1)
                if len(parts) == 2:
                    cat_name = parts[0].strip()
                    cat_msg = parts[1].strip()
                    admin_categories[cat_name] = cat_msg
                    if cat_name not in claimed_stats:
                        claimed_stats[cat_name] = 0
                    save_data()
                    send_message(chat_id, f"✅ <b>ক্যাটাগরি বাটন যুক্ত হয়েছে!</b>\n\n<b>বাটন:</b> {cat_name}\n<b>মেসেজ:</b> {cat_msg}")
                else:
                    send_message(chat_id, "❌ <b>ফরম্যাট ভুল!</b> এভাবে লিখুন:\n<code>/add বাটনের নাম | মেসেজ</code>")
            except Exception as e:
                send_message(chat_id, f"ত্রুটি: {e}")
            return
            
        elif text.startswith("/del "):
            cat_name = text[5:].strip()
            if cat_name in admin_categories:
                del admin_categories[cat_name]
                save_data()
                send_message(chat_id, f"🗑️ '{cat_name}' বাটনটি মুছে ফেলা হয়েছে।")
            else:
                send_message(chat_id, "❌ এই নামের কোনো বাটন পাওয়া যায়নি।\nসঠিক নাম দেখতে <code>/analysis</code> লিখুন।")
            return
            
        elif text == "/analysis":
            total_users = len(db)
            completed_users = sum(1 for u in db.values() if u["referral_count"] >= REQUIRED_REFERRALS)
            
            stats_text = ""
            if claimed_stats:
                for cat, count in claimed_stats.items():
                    stats_text += f"• {cat}: {count} বার নেওয়া হয়েছে\n"
            else:
                stats_text = "কোনো ডেটা নেই (ইউজাররা এখনো কিছু নেয়নি)।"

            buttons_list = "\n".join([f"• {k}" for k in admin_categories.keys()]) if admin_categories else "কোনো বাটন এড করা নেই।"

            analysis_msg = f"📊 <b>বট অ্যানালাইসিস ও পরিসংখ্যান:</b>\n\n" \
                           f"👥 <b>মোট একটিভ ইউজার:</b> {total_users} জন\n" \
                           f"✅ <b>টাস্ক বা রেফারেল পূর্ণ করেছে:</b> {completed_users} জন\n\n" \
                           f"📋 <b>বর্তমান লাইভ বাটন সমূহ:</b>\n{buttons_list}\n\n" \
                           f"📈 <b>ইউজাররা কে কি নিয়েছে (বাটন ক্লিক হিস্ট্রি):</b>\n{stats_text}"
            send_message(chat_id, analysis_msg)
            return
            
        elif text == "/admin":
            send_message(chat_id, "👑 <b>👑 এডমিন প্যানেল কমান্ডস:</b>\n\n"
                                   "1️⃣ বাটন যোগ করতে: <code>/add বাটনের নাম | মেসেজ</code>\n"
                                   "2️⃣ বাটন মুছতে: <code>/del ক্যাটাগরির নাম</code>\n"
                                   "3️⃣ ইউজার ডাটা ও এনালাইসিস দেখতে: <code>/analysis</code>")
            return

    if text.startswith("/start"):
        args = text.split()
        if len(args) > 1:
            try:
                referrer_id = int(args[1])
                if referrer_id != user_id and db[user_id]["referred_by"] is None and not db[user_id]["is_verified"]:
                    db[user_id]["referred_by"] = referrer_id
                    save_data()
            except ValueError:
                pass

        inline_keyboard = []
        for ch in CHANNELS:
            inline_keyboard.append([{"text": ch["name"], "url": ch["url"]}])
        inline_keyboard.append([{"text": "✅ Joined (জয়েন করেছি)", "callback_data": "check_joined"}])

        send_message(chat_id, "👋 <b>হ্যালো! বটটি ব্যবহার করতে আপনাকে আমাদের অফিসিয়াল চ্যানেলগুলোতে জয়েন করতে হবে।</b>\n\n"
                               "নিচের চ্যানেলগুলোতে জয়েন করে <b>'Joined'</b> বাটনে ক্লিক করুন:", {"inline_keyboard": inline_keyboard})

def handle_callback(callback):
    clb_id = callback["id"]
    user_id = callback["from"]["id"]
    chat_id = callback["message"]["chat"]["id"]
    message_id = callback["message"]["message_id"]
    data = callback["data"]
    first_name = callback["from"].get("first_name", "User")

    init_user(user_id, first_name)

    if data == "check_joined":
        if is_user_joined_all(user_id):
            if not db[user_id]["is_verified"]:
                ref_id = db[user_id]["referred_by"]
                if ref_id and ref_id in db:
                    db[ref_id]["referral_count"] += 1
                    try:
                        send_message(ref_id, f"🎉 <b>নতুন রেফার সফল!</b>\nআপনার লিংকের মাধ্যমে একজন মেম্বার জয়েন করেছে।\nবর্তমান রেফার সংখ্যা: {db[ref_id]['referral_count']} টি।")
                    except:
                        pass
                db[user_id]["is_verified"] = True
                save_data()
            
            send_main_page(chat_id, message_id, user_id)
            answer_callback_query(clb_id, "ভেরিফিকেশন সফল!")
        else:
            answer_callback_query(clb_id, "❌ আপনি এখনও আমাদের প্রয়োজনীয় চ্যানেলে জয়েন করেননি!", show_alert=True)

    elif data == "refresh_count":
        try:
            send_main_page(chat_id, message_id, user_id)
            answer_callback_query(clb_id, "রেফার কাউন্ট আপডেট করা হয়েছে!")
        except:
            answer_callback_query(clb_id, "ইতিমধ্যে আপডেট করা আছে।")

    elif data == "click_access":
        current_refs = db[user_id]["referral_count"]
        if current_refs >= REQUIRED_REFERRALS:
            if not admin_categories:
                answer_callback_query(clb_id, "⚠️ দুঃখিত, এডমিন এখনো কোনো ডাটা বা বাটন সেট করেননি। দয়া করে অপেক্ষা করুন।", show_alert=True)
                return
                
            # HTML ট্যাগ ব্যবহার করা হয়েছে এবং কোডের REQUIRED_REFERRALS অনুযায়ী মান অটোমেটিক বসবে
            text = f"🎉 <b>অভিনন্দন!</b> আপনি সফলভাবে এটি Access করতে পেরেছেন।\n\n" \
                   f"👇 আপনার <b>{REQUIRED_REFERRALS} টি রেফার</b> পূর্ণ হয়েছে। নিচে থেকে এখন আপনি কী নিতে চান তা সিলেক্ট করুন:"
            
            inline_keyboard = []
            for i, cat_name in enumerate(admin_categories.keys()):
                inline_keyboard.append([{"text": cat_name, "callback_data": f"cat_{i}"}])
            
            edit_message_text(chat_id, message_id, text, {"inline_keyboard": inline_keyboard})
            answer_callback_query(clb_id, "এক্সেস অনুমোদিত!")
        else:
            answer_callback_query(clb_id, f"❌ আপনার এখনও {REQUIRED_REFERRALS} টি রেফার পূর্ণ হয়নি!\nবর্তমান রেফার: {current_refs} টি।", show_alert=True)

    elif data.startswith("cat_"):
        try:
            cat_index = int(data[4:])
            categories_list = list(admin_categories.keys())
            
            if 0 <= cat_index < len(categories_list):
                cat_name = categories_list[cat_index]
                msg_text = admin_categories[cat_name]
                send_message(chat_id, msg_text)
                
                if cat_name not in db[user_id]["items_claimed"]:
                    db[user_id]["items_claimed"].append(cat_name)
                
                if cat_name in claimed_stats:
                    claimed_stats[cat_name] += 1
                else:
                    claimed_stats[cat_name] = 1
                
                save_data()
                answer_callback_query(clb_id, "পাঠানো হয়েছে!")
            else:
                answer_callback_query(clb_id, "❌ বাটনটি খুঁজে পাওয়া যায়নি বা আপডেট করা হয়েছে।", show_alert=True)
        except Exception as e:
            answer_callback_query(clb_id, "❌ কোনো একটি ত্রুটি ঘটেছে!", show_alert=True)

def main():
    load_data()
    offset = 0
    print("Bot is running successfully...")
    while True:
        try:
            payload = {"offset": offset, "timeout": 20, "allowed_updates": ["message", "callback_query", "chat_join_request"]}
            res = make_request("getUpdates", payload)
            if res and res.get("ok"):
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update:
                        handle_message(update["message"])
                    elif "callback_query" in update:
                        handle_callback(update["callback_query"])
                    elif "chat_join_request" in update:
                        handle_join_request(update["chat_join_request"])
        except KeyboardInterrupt:
            print("Bot stopped.")
            break
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    main()