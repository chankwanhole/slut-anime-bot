import interactions
import requests
import mysql.connector
import asyncio
import datetime
import random
import anthropic
from urllib.parse import quote
from mysql.connector import errorcode
from interactions import slash_command, SlashContext, OptionType, slash_option, AutocompleteContext, Member
from bs4 import BeautifulSoup

bot = interactions.Client()
cnx = mysql.connector.connect(user='root', password='00000000', host='127.0.0.1', database='anime')
BOT_TOKEN = "BOT_TOKEN"
client = anthropic.Anthropic( api_key = "API_KEY" )


async def check_updates():
    print('checked')

    cursor = cnx.cursor()

    updated = 0
    no_update = 0

    try:
        cursor.execute("SELECT * FROM subscriptions")
        result = cursor.fetchall()

        for row in result:
            url = row[2]
            response = requests.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            if "anime1.me" in url:
                main_element = soup.find('main', id='main')

                if main_element:
                    article_element = main_element.find('article')

                    if article_element:
                        header_element = article_element.find('header', class_='entry-header')

                        if header_element:
                            h2_element = header_element.find('h2', class_='entry-title')

                            if h2_element:
                                title = h2_element.text
                                if title != row[3]:
                                    cursor.execute("UPDATE subscriptions SET sub_anime_name = %s WHERE sub_url = %s AND sub_user =  %s", (title, url, row[1]))
                                    cursor.execute("INSERT INTO subscriptions_log (sub_user, sub_url, sub_anime_name, action, action_time) VALUES (%s, %s, %s, 'UPDATE', NOW())", (row[1], url, title))
                                    cnx.commit()
                                    updated += 1
                                    await notify_subscriber(row[1], row[4], title, url)
                                else:
                                    no_update += 1
                            else:
                                print("Error: h2 element not found.")
                        else:
                            print("Error: header element not found.")
                    else:
                        print("Error: article element not found.")
                else:
                    print("Error: main element not found.")
            elif "myself-bbs.com" in url:
                div_element = soup.find('div', id='pt')

                if div_element:
                    div_element_2 = div_element.find('div', class_="z")

                    if div_element_2:
                        a_element = div_element_2.find('a', href=lambda href: href and "thread" in href)
                        if a_element:
                            meta_element = soup.find('meta', {"name": "keywords"})
                            if meta_element:
                                title = meta_element['content']
                                if title != row[3]:
                                    cursor.execute("UPDATE subscriptions SET sub_anime_name = %s WHERE sub_url = %s", (title, url))
                                    cursor.execute("INSERT INTO subscriptions_log (sub_user, sub_url, sub_anime_name, action, action_time) VALUES (%s, %s, %s, 'UPDATE', NOW())", (row[1], url, title))
                                    cnx.commit()
                                    updated += 1
                                    await notify_subscriber(row[1], row[4], title, url)
                                else:
                                    no_update += 1
                            else:
                                print("Error: meta element not found.")
                        else:
                            print("Error: a element not found.")
                    else:
                        print("Error: div element 2 not found.")
                else:
                    print("Error: div element not found.")
    except mysql.connector.Error as e:
        print("Error: " + str(e))
    finally:
        print("updated: " + str(updated) + ", no update: " + str(no_update))
        print("last check time: " + str(datetime.datetime.now()))
        cnx.commit()
        cursor.close()
        await asyncio.sleep(60*10)


@interactions.listen()
async def on_startup():
    print('Logged in as {0.user}'.format(bot))
    while True:
        await asyncio.create_task(check_updates())

@slash_command(name="anime_subscribe", description="subscribe動漫（只接受anime1同myself動漫）")
@slash_option(
    name="anime_url",
    description="請選擇此選項並貼上動漫網址（只接受anime1同myself動漫）",
    opt_type=OptionType.STRING
)
async def anime_subscribe(ctx: SlashContext, anime_url: str):
    user_id = ctx.author.id
    user_channel = ctx.channel.id
    anime_url = anime_url.strip()

    if "anime1.me" in anime_url or "myself-bbs.com" in anime_url:
        if "anime1.me" in anime_url:
            res = subscribe_from_anime1(anime_url, user_id, user_channel)
            await ctx.send(res)
        else:
            res = subscribe_from_myself(anime_url, user_id, user_channel)
            await ctx.send(res)
    else:
        await ctx.send("讀取錯誤（只接受anime1同myself動漫）")

@slash_command(name="anime_list_subscriptions", description="列出所有動漫subscriptions")
async def list_subscriptions(ctx: SlashContext):
    user_id = ctx.author.id
    res = get_subscriptions(user_id)
    await ctx.send(res)

@slash_command(name="anime_unsubscribe", description="unsubscribe動漫")
@slash_option(
    name="anime_name",
    description="請選擇此選項並貼上動漫網址（只接受anime1同myself動漫）",
    opt_type=OptionType.STRING,
    autocomplete=True
)
async def anime_unsubscribe(ctx: SlashContext, anime_name: str):
    user_id = ctx.author.id
    anime_url = anime_name
    anime_url = anime_url.strip()
    res = delete_subscription(anime_url, user_id)
    await ctx.send(res)

@anime_unsubscribe.autocomplete("anime_name")
async def anime_name_autocomplete(ctx: AutocompleteContext):
    user_id = ctx.author.id
    cursor = cnx.cursor()
    user_id = str(user_id)
    cursor.execute("SELECT sub_url, sub_anime_name FROM subscriptions WHERE sub_user = %s", (user_id,))
    results = cursor.fetchall()
    cursor.close()
    cnx.commit()

    choices = []

    for result in results:
        choice = {
            "name": result[1],
            "value": result[0]
        }
        choices.append(choice)
    
    await ctx.send(choices)

@slash_command(name="anime_unsubscribe_all", description="unsubscribe所有動漫")
async def anime_unsubscribe_all(ctx: SlashContext):
    user_id = ctx.author.id
    res = delete_all_subscriptions(user_id)
    await ctx.send(res)

@slash_command(name="anime_help", description="subscribe動漫使用說明")
async def anime_help(ctx: SlashContext):
    await ctx.send('請參閱以下檔案: \n<https://shorturl.at/fwyMU>')

@slash_command(name="anime_change_channel", description="更改動漫subscription通知channel")
async def anime_change_channel(ctx: SlashContext):
    user_id = ctx.author.id
    user_channel = ctx.channel.id
    res = change_channel(user_id, user_channel)
    await ctx.send(res)

@slash_command(name="google", description="Google")
@slash_option(
    name="keywords",
    description="Google search",
    opt_type=OptionType.STRING
)
async def google(ctx: SlashContext, keywords: str):
    keywords = quote(keywords, safe='')
    url = '<https://letmegooglethat.com/?q=' + keywords +'>'
    await(ctx.send(url))

@slash_command(name="fuck", description="屌你老母")
@slash_option(
    name="user",
    description="即將被屌嘅老友",
    required=True,
    opt_type=OptionType.USER
)
async def fuck(ctx: SlashContext, user: Member):
    cursor = cnx.cursor()

    try:
        cursor.execute("SELECT content FROM sentences WHERE type = 2")
        result = cursor.fetchall()

        sentences = []
        for row in result:
            sentences.append(row[0])
        sentence = random.choice(sentences)

        await ctx.send(f"{user.mention}" + " " + sentence)

    except mysql.connector.Error as e:
        if e.errno == errorcode.ER_DUP_ENTRY:
            return "Error: Duplicate entry."
        else:
            return "Error: " + str(e)
        
    finally:
        cnx.commit()
        cursor.close()

@slash_command(name="chat", description="Claude AI")
@slash_option(
    name="prompt",
    description="輸入問題",
    required=True,
    opt_type=OptionType.STRING
)
async def chat(ctx: SlashContext, prompt: str):
    # make prompt to string

    message = client.messages.create(
        model="claude-instant-1.2",
        max_tokens=4000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    message = message.content
    message = ''.join(message)

    await ctx.send(message)
        

def subscribe_from_anime1(url, user_id, user_channel):
    try:
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        main_element = soup.find('main', id='main')

        if main_element:
            article_element = main_element.find('article')

            if article_element:
                header_element = article_element.find('header', class_='entry-header')

                if header_element:
                    h2_element = header_element.find('h2', class_='entry-title')

                    if h2_element:
                        res = insert_subscription(url, h2_element.text, user_id, user_channel)
                        return res
                    else:
                        return "Error: h2 element not found."
                else:
                    return "Error: header element not found."
            else:
                return "Error: article element not found."
        else:
            return "Error: main element not found."

    except requests.exceptions.RequestException as e:
        return "Error: " + str(e)

def subscribe_from_myself(url, user_id, user_channel):
    try:
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        div_element = soup.find('div', id='pt')

        if div_element:
            div_element_2 = div_element.find('div', class_="z")

            if div_element_2:
                a_element = div_element_2.find('a', href=lambda href: href and "thread" in href)
                if a_element:
                    meta_element = soup.find('meta', {"name": "keywords"})
                    if meta_element:
                        title = meta_element['content']
                        res = insert_subscription(url, title, user_id, user_channel)
                        return res
                    else:
                        return "Error: meta element not found."
                else:
                    return "Error: a element not found."
            else:
                return "Error: div element 2 not found."
        else:
            return "Error: div element not found."
    except requests.exceptions.RequestException as e:
        return "Error: " + str(e)

def insert_subscription(url, title, user_id, user_channel):
    cursor = cnx.cursor()

    try:
        user_id = str(user_id)
        user_channel = str(user_channel)
        cursor.execute("SELECT * FROM subscriptions WHERE sub_url = %s AND sub_user = %s", (url, user_id))
        result = cursor.fetchall()
        if len(result) > 0:
            return "你之前subscribe過呢套動漫喇！"
        
        cursor.execute("UPDATE subscriptions SET sub_channel = %s WHERE sub_user = %s", (user_channel, user_id))
        cursor.execute("INSERT INTO subscriptions_log (sub_user, sub_channel, action, action_time) VALUES (%s, %s, 'UPDATE', NOW())", (user_id, user_channel))

        cursor.execute("INSERT INTO subscriptions (sub_user, sub_url, sub_anime_name, sub_channel, last_modified_time) VALUES (%s, %s, %s, %s, NOW())", (user_id, url, title, user_channel))
        cursor.execute("INSERT INTO subscriptions_log (sub_user, sub_url, sub_anime_name, sub_channel, action, action_time) VALUES (%s, %s, %s, %s, 'INSERT', NOW())", (user_id, url, title, user_channel))

        if cursor.rowcount == 1:
            return "subscribe成功！"

    except mysql.connector.Error as e:
        if e.errno == errorcode.ER_DUP_ENTRY:
            return "Error: Duplicate entry."
        else:
            return "Error: " + str(e)
        
    finally:
        cnx.commit()
        cursor.close()

def get_subscriptions(user_id):
    cursor = cnx.cursor()

    try:
        user_id = str(user_id)
        cursor.execute("SELECT * FROM subscriptions WHERE sub_user = %s", (user_id,))
        result = cursor.fetchall()

        if len(result) == 0:
            return "你冇subscribe任何動漫。"

        result_str = "你已subscribe " + str(len(result)) + "套動漫：\n"
        for row in result:
            result_str += str(result.index(row) + 1) + '. ' + row[3] + ' ' + '<' + row[2] + '>' + '\n'
        
        return result_str
    
    except mysql.connector.Error as e:
        return "Error: " + str(e)
    
    finally:
        cnx.commit()
        cursor.close()

def delete_subscription(url, user_id):
    cursor = cnx.cursor()

    try:
        user_id = str(user_id)
        cursor.execute("DELETE FROM subscriptions WHERE sub_url = %s AND sub_user = %s", (url, user_id))
        cursor.execute("INSERT INTO subscriptions_log (sub_user, sub_url, action, action_time) VALUES (%s, %s, 'DELETE', NOW())", (user_id, url))

        if cursor.rowcount >= 1:
            return "unsubscribe成功！"

    except mysql.connector.Error as e:
        return "Error: " + str(e)
    
    finally:
        cnx.commit()
        cursor.close()

def delete_all_subscriptions(user_id):
    cursor = cnx.cursor()

    try:
        user_id = str(user_id)

        cursor.execute("SELECT * FROM subscriptions WHERE sub_user = %s", (user_id,))
        result = cursor.fetchall()
        if len(result) == 0:
            return "你冇subscribe任何動漫。"

        cursor.execute("DELETE FROM subscriptions WHERE sub_user = %s", (user_id,))
        cursor.execute("INSERT INTO subscriptions_log (sub_user, action, action_time) VALUES (%s, 'DELETE_ALL', NOW())", (user_id,))

        if cursor.rowcount >= 1:
            return "unsubscribe所有動漫成功！"

    except mysql.connector.Error as e:
        return "Error: " + str(e)
    
    finally:
        cnx.commit()
        cursor.close()

def change_channel(user_id, user_channel):
    cursor = cnx.cursor()

    try:
        user_id = str(user_id)
        user_channel = str(user_channel)
        cursor.execute("UPDATE subscriptions SET sub_channel = %s WHERE sub_user = %s", (user_channel, user_id))
        cursor.execute("INSERT INTO subscriptions_log (sub_user, sub_channel, action, action_time) VALUES (%s, %s, 'UPDATE', NOW())", (user_id, user_channel))

        if cursor.rowcount >= 1:
            return "更改subscribe動漫通知channel成功！新嘅通知channel係 <#" + user_channel + ">。"

    except mysql.connector.Error as e:
        return "Error: " + str(e)
    
    finally:
        cnx.commit()
        cursor.close()

async def notify_subscriber(user_id, user_channel, title, url):
    text_channel = bot.get_channel(int(user_channel))
    print('Notify user: ' + user_id + ' in channel: ' + user_channel + ' with title: ' + title + ' and url: ' + url)
    await text_channel.send('<@' + user_id + '> ' + title + ' 有更新！<' + url + '>')

bot.start(BOT_TOKEN)
