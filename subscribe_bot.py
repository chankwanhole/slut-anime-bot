import interactions
import requests
import mysql.connector
import asyncio
import datetime
from urllib.parse import quote
from mysql.connector import errorcode
from interactions import slash_command, SlashContext, OptionType, slash_option, AutocompleteContext, Member
from bs4 import BeautifulSoup

bot = interactions.Client()
cnx = mysql.connector.connect(user='root', password='00000000', host='127.0.0.1', database='anime')

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
    await ctx.send(f"{user.mention}我唔撚柒鳩屌你個冚家剷含撚笨柒個老母個生滋甩毛嘅爛臭化花柳白濁梅毒性冷感閪都唔撚柒得陰陽面邊大邊細豬閪燉糯米雙番閪遮面長短腳谷精上腦陽萎笨柒周頭發炎陰蝨周圍跳白竇臭滴蟲入鳩祖宗十八代食屎撈屄周揈揈白痴戇鳩閪 我屌你老母十八代柒頭撚樣系垃圾狗屎on鳩formula無撚用到喊數字柒頭死全家仆你個臭街一見到就想嘔番曬大大大前日嘅早餐生出黎害鳩人咁柒就咪撚出黎獻世啦一碌柒咁onj幾撚有心機都無鳩用啦屌你老母芝士漢堡柒頭皮 屌你老母 芝士漢堡屌你老豆 宿埋一舊 屌你家姐 落雨擔遮 屌你家姐 快過火車 屌你呀爺 笑口畸畸 屌你呀麻 泰國喇嘛屌你呀妹碌柒崩潰屌你阿哥 好過渣波 屌你屎忽化痰止咳 屌你個仔 屎忽扭計 屌你個咀 刷牙唔用涮口水 屌你老母仆街陷家產食屎收皮啦屌你. 戇撚鳩鳩食撚晒賓州咁屌你老母咁既仆街死樣. 吹撚脹? 你係生出黎俾我屌撚柒嫁啦仆街陷家產. 屌足你十世,屌你老母正仆街陷家產屌你祖宗十八代仆街含家產你老母生花柳,你老豆生龜頭癌呀柒仔收皮吧啦施主收皮啦傻仔你老母日日要比人屌就係因為你呢d咁既傻仔呀慘過做雞同企街證明你條契弟祖宗十八代都作孽,生你件仆街仔,九成九冇屎忽我頂你個肺插你個胃按你肚池機關制屌你老祖十八代 代代冇春代含撚啦你仆街含家產九歲扮做雞 十歲同人玩結婚十一歲學人做飛仔 十二歲扮做鴨十九歲學人上廿歲去夜總會二十一歲去做鴨二十二歲生花柳愛滋仆街死食揉屎啦屌你老母祖宗十鳩撚春鳩柒代撚頭西屎啦!屌你老母斬你全家你老母老婆比我強姦十次八次啦絕子絕孫啦你正一狗雜種我屌你老母啦你老母一定用屎餵大你條死戇鳩仔 你呢條敗類你條撚 樣想唔屌你都唔得, 你個臭貨老母同野狗狗合生埋你呢仆街仔廢柴屌你祖宗18代有愛滋有爺生無家教不知所謂多行不義必自斃屌你老母仆你個街杏家產死傻西屌你老母仆街啦你阻撚住晒個地球轉 正一憾家剷屌你老母臭花西! 你老豆老母性器官一定有問題啦 生你條撚樣出黎冇賓周冇精蟲死基佬我屌鳩柒你就梗架啦我係鐘意屌鳩你祖宗18個春袋呀你吹撚柒碌我帳呀﻿")

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

bot.start("MTIxMTU1ODcyNzE3ODY0OTY1MA.GxA4hW.k9h72c-538Yg1lh0W3RUB_844DOtAsmPnDALiw")
