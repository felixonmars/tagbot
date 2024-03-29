#coding:utf-8
import tweepy
from tweepy.streaming import StreamListener, Stream
import sqlite3, re
import memcache
import datetime
import random
from types import ListType

class MemCache:
    def __enter__(self):
        self.mc = memcache.Client(['unix:/tmp/memcached.sock'], debug=0)
        return self.mc
    def __exit__(self, type, value, traceback):
        self.mc.disconnect_all()

def check_user(func):
    def __check(*args, **kwargs):
        self, user, replyto = args[:3]
        try:
            nick = self.get_nick(user, forcecheck = True)
            return func(*args, nick = nick, **kwargs)
        except NameError:
            params = dict(
                            replyto = replyto,
                            user = user,
                        )
            self.tweet(u"@%(replyto)s 这个世界上还木有叫 @%(user)s 的猫儿呢.." % params)
    return __check

class BaseHandler:
    def __init__(self, api):
        self.api = api
        
    def get_nick(self, user, forcecheck = False):
        with MemCache() as mc:
            key = user.encode("utf-8")
            try:
                nick = mc.get(key)
            except:
                nick = ""
            if nick:
                return nick
            else:
                try:
                    a = self.api.get_user(user)
                    a = a.name
                except:
                    if forcecheck:
                        raise NameError
                    a = ""
            nick = a
            try:
                mc.set(key, nick, time = 86400)
            except:
                pass
        return nick
    
    def tweet(self, text):
        text += u"(现在是" + str(datetime.datetime.now()) + ")"
        print "Tweet: " + text,
        try:
            self.api.update_status(text)
            print "Success"
        except:
            print "Failed"

class TagHandler(BaseHandler):
    nums = u"① ② ③ ④ ⑤ ⑥ ⑦ ⑧ ⑨ ⑩"
    nums = nums.split()
    
    def __init__(self, api, botname):
        BaseHandler.__init__(self, api)
        self.botname = botname
        self.db = sqlite3.connect("bot.db")
        self.c = self.db.cursor()
        try:
            self.c.execute("CREATE TABLE tags(user str, tags str)")
        except sqlite3.OperationalError:
            pass
    
    @check_user
    def save_tag(self, user, replyto, tag, nick):
        self.c.execute("SELECT tags FROM tags WHERE user = ?", (user.lower(), ))
        l = self.c.fetchone()
        if l == None:
            self.c.execute("INSERT INTO tags(user, tags) VALUES(?,?)",
                           (user.lower(), str([{
                                            "tag": tag,
                                            "commenter": replyto,
                                            "added": datetime.datetime.now()
                                            }])))
            params = dict(
                            replyto = replyto,
                            user = user,
                            tag = tag,
                            nick = nick
                        )
            tweetstr = u"@%(replyto)s 给【%(nick)s @%(user)s 】添加Tag:%(tag)s 成功了喵<(=^_^=)>" % params
        else:
            tags = eval(l[0])
            tagvals = []
            commenters = []
            for atag in tags:
                commenters.append(atag["commenter"])
                tagvals.append(atag["tag"])
            
            goon = True
            if replyto in commenters:
                print "User already Tagged this target, ignoring"
                params = dict(
                            replyto = replyto,
                            user = user,
                            tag = tag,
                            nick = nick
                         )
                tweetstr = u"@%(replyto)s 乃已经给【%(nick)s %(user)s 】添加过Tag啦<(=￣▽￣=)>" % params
                goon = False
                
            if goon and tag in tagvals:
                print "Tag already exists, ignoring"
                params = dict(
                            replyto = replyto,
                            user = user,
                            tag = tag,
                            nick = nick
                         )
                tweetstr = u"@%(replyto)s 【%(nick)s %(user)s 】已经有这个Tag:%(tagac)s 啦<(=￣▽￣=)>" % params
                goon = False
            
            if goon:
                tags.append({
                                "tag": tag,
                                "commenter": replyto,
                                "added": datetime.datetime.now()
                            })
                            
                #tags.sort(key = lambda x:x["added"])
                
                if len(tags) > 10:
                    tags.remove(tags[0])
                
                newtags = str(tags)
                self.c.execute("UPDATE tags SET tags = ? WHERE user = ?",
                               (newtags, user.lower()))
                params = dict(
                            replyto = replyto,
                            user = user,
                            tag = tag,
                            nick = nick
                         )
                tweetstr = u"@%(replyto)s 给【%(nick)s @%(user)s 】添加Tag:%(tag)s 成功了喵<(=^_^=)>" % params
                
        self.db.commit()
        self.tweet(tweetstr)
    
    @check_user
    def get_tag(self, user, replyto, nick):
        self.c.execute("SELECT tags FROM tags WHERE user = ?", (user.lower(), ))
        l = self.c.fetchone()
        if l is None or l[0] == "[]":
            params = dict(
                            replyto = replyto,
                            user = user,
                            botname = self.botname,
                            nick = nick
                         )
            tweetstr = u"%(nick)s @%(user)s 还没有Tag哦! 发送 \"@%(botname)s %(user)s=您想添加的Tag\" 立刻给Ta添加Tag吧<(=^_^=)>" % params
            if replyto:
                tweetstr = u"@%(replyto)s " % params + tweetstr
            
        else:
            tags = eval(l[0])
            tagvals = [tag["tag"] for tag in tags]
            tags_formatted = "".join(["".join(x) for x in zip(self.nums[:len(tags)], tagvals)])
            params = dict(
                            replyto = replyto,
                            user = user,
                            tags = tags_formatted,
                            nick = nick
                         )
            tweetstr = u"【%(nick)s @%(user)s 】的推特Tag:%(tags)s" % params
            if replyto:
                tweetstr = u"@%(replyto)s " % params + tweetstr
        
        self.tweet(tweetstr)
    
    def del_tag(self, user, tag):
        self.c.execute("SELECT tags FROM tags WHERE user = ?", (user.lower(), ))
        l = self.c.fetchone()
        if l is None or l[0] == "[]":
            params = dict(
                            user = user,
                            nick = nick
                         )
            tweetstr = u"@%(user)s %(nick)s乃还没有Tag呢<(=￣▽￣=)>" % params
            
        else:
            tags = eval(l[0])
            found = False
            
            for xtag in tags:
                if xtag["tag"] == tag:
                    found = True
                    break
            
            if not found:
                params = dict(
                            user = user,
                            nick = nick
                         )
                tweetstr = u"@%(user)s %(nick)s乃没有这个Tag<(=￣▽￣=)>" % params
            else:
                tags.remove(xtag)
                
                self.c.execute("UPDATE tags SET tags = ? WHERE user = ?",
                               (str(tags), user.lower()))
                params = dict(
                            user = user,
                            tag = tag,
                         )
                tweetstr = u"@%(user)s 乃的Tag:%(tag)s 成功删除了喵<(=^_^=)>" % params
                
        self.db.commit()
        self.tweet(tweetstr)
        
class CustomHandler(BaseHandler):
    def detect(self, user, text):
        normalarray = {
            u"傲娇": u"@%(user)s 哼! 我才不是傲娇呢! %(nick)s才是傲娇!",
            u"卖萌": u"@%(user)s 喵<(=^_^=)>",
            u"猫老师": [
                        u"@%(user)s 猫老师 @_ym 是好猫<(=^_^=)>",
                        u"@%(user)s 要蹭蹭猫老师 @_ym 哦<(≧︶)￣▽￣=)>ゞ",
                    ],
            u"交尾": u"@%(user)s 变态! 叫%(nick)s的人我讨厌死了!",
            u"求包养": u"@%(user)s 很遗憾, 你还没有资格!",
            u"求交往": u"@%(user)s 我拒绝!",
            u"求合体": u"@%(user)s 我来组成头部<(=^_^=)>",
            u"求治愈": u"@%(user)s 喵<(=^_^=)>",
            u"求虐": u"@%(user)s Pia!<(=ｏ‵-′)ノ☆",
            u"苗子": u"@%(user)s 苗子 @mys_721tx 是大坏猫，摔！",
            u"蹭": u"@%(user)s 蹭蹭 %(nick)s <(≧︶)￣▽￣=)>ゞ",
            u"yoo": u"@%(user)s <(/▽＼=)>",
            u"踩": u"@%(user)s <(=￣︿￣)︵θ︵θ︵θ︵θ︵☆(＞口＜=)>",
            u"笨蛋": u"@%(user)s 乃是笨蛋<(/▽＼=)>",
            u"黄鱼": u"@%(user)s 偶最喜欢吃小黄鱼啦喵<(=￣﹃￣=)>",
            u"吃货": u"@%(user)s 偶好想吃小黄鱼喵ˋ<(=° ▽、°=)>",
            u"痴": u"@%(user)s <(=˚　˚)",
            u"近视": u"@%(user)s 小心近视喵<(=㋺ω㋺=)>",
            u"哈": u"@%(user)s <(=￣▽￣=)>",
            u"热": u"@%(user)s 热死猫啦<(╭||￣▽￣)╮",
            u"样子": u"@%(user)s 偶是像猫老师一样的奶牛猫哦<(=^_^=)>",
            u"程序": u"@%(user)s 笨猫 @felixonmars 是首席程序猫<(=｀ェ´=)>",
            u"太阳": u"@%(user)s 晒太阳好舒服喵～<(O_　_)0。゜zｚＺ",
            u"困": u"@%(user)s <(O_　_)0。゜zｚＺ",
            u"人": u"@%(user)s 愚蠢的人类<(=￣▽￣=)>",
            u"戳": [
                    u"@%(user)s 提问：一个愚蠢的人类掉到河里，它从河里爬上来，头发却没湿，为什么？",
                    u"@%(user)s 提问：谁是推上最话痨的人呢喵？",
                    u"@%(user)s 房间里有十根点着的蜡烛，被风吹灭了九根，第二天还剩几根",
                    u"@%(user)s 反戳→)╥﹏╥=)>",
                    u"@%(user)s <(=ㄒ‸ㄒ=)>",
                    u"@%(user)s 反戳菊花<(= ￣y▽￣)╭→)※(=v＃°皿°)真·爆菊奥义",
                    u"@%(user)s 有个愚蠢的人类摸摸偶的头，乃猜偶说了什么<(=￣▽￣=)>",
                    u"@%(user)s 什么东西外表是红的，最核心的东西是黑的？",
                    ],
            u"test": u"@%(user)s 成功*:.☆\<(=￣▽￣=)>/$:*.°★*~",
            u"光头": u"@%(user)s 勉强对了喵",
            u"吴克": u"@%(user)s <(=→_→=)>对了喵",
            u"冷": u"@%(user)s 扔冰块，开空调（ε=ε=ε=┏<(=゜ロ゜)┛",
            u"木耳": u"@%(user)s 吃掉木耳<(=￣﹃￣=)>",
            u"⑨": u"@%(user)s %(nick)s 就是个⑨",
            u"9": u"@%(user)s ╮<(=￣▽￣=)>╭",
            u"不知道": u"@%(user)s 愚蠢的人类<(=￣ˇ￣=)>",
            u"愚蠢的人类": u"@%(user)s 嗯，人类必须愚蠢<(=￣ˇ￣=)>",
            u"摸摸": u"@%(user)s 愚蠢的人类（<(=￣ˇ￣=)>",
            u"党": u"@%(user)s <(=▼-▼=)>☭",
            u"荔枝": u"@%(user)s 其实你可以反动一点喵<(=→_→=)>",
            u"土共": u"@%(user)s 五猫党才是世界上可以独裁人类的党喵<(=╯▽╰=)>",
            u"黑猫": u"@%(user)s Pia!<(=ｏ‵-′)ノ☆ @hitigon ",
            u"摔猫": u"@%(user)s 摔%(nick)s",
            }
            
        params = dict(
                        user = user,
                        nick = self.get_nick(user),
                     )
        
        for key in normalarray.keys():
            if key in text:
                tweetstr = normalarray[key]
                if type(tweetstr) is ListType:
                    tweetstr = random.choice(tweetstr)
                self.tweet(tweetstr % params)
                return
        if text == "/pia" or text == "/pia!":
            self.tweet(u"@%(user)s 用力回Pia!<(=ｏ‵-′)ノ☆ %(nick)s @%(user)s ! " % params)
            return
        if text[:4] == "/pia":
            target = text[4:].strip()
            if target != "@" and target[0] == "@":
                target = target[1:]
            params["target"] = target
            params["targetnick"] = self.get_nick(target)
            self.tweet(u"@%(user)s 大力Pia!<(=ｏ‵-′)ノ☆ %(targetnick)s @%(target)s !" % params)
            return
        self.tweet(u"@%(user)s 呜..%(nick)s说的话我怎么听不懂呢.." % params)
            

class Listener(StreamListener):
    def __init__(self, botname, taghandler, customhandler):
        self.botname = botname
        self.rsettag = re.compile(u"^@%s +@?([a-zA-Z0-9_-]+) *[\=\＝] *([^\s]+)$" % self.botname, re.IGNORECASE)
        self.rgettag = re.compile(u"^@%s +@?([a-zA-Z0-9_-]+) *$" % self.botname, re.IGNORECASE)
        self.rdeltag = re.compile(u"^@%s +\/del +([^\s]+) *$" % self.botname, re.IGNORECASE)
        StreamListener.__init__(self)
        self.taghandler = taghandler
        self.customhandler = customhandler
    
    def on_status(self, status):
        text = status.text.strip()
        replyto = status.user.screen_name
        print "Original tweet:", replyto, ":", text
        
        prefix = "@%s " % self.botname
        
        settag = self.rsettag.findall(text)
        if len(settag):
            user, tag = settag[0]
            print "Setting tag for user %s: %s" % (user, tag)
            self.taghandler.save_tag(user, replyto, tag)
            return
            
        gettag = self.rgettag.findall(text)
        if len(gettag):
            user = gettag[0]
            print "Getting tag for user %s" % (user, )
            self.taghandler.get_tag(user, replyto)
            return
            
        deltag = self.rdeltag.findall(text)
        if len(deltag):
            user = status.user.screen_name
            tag = deltag[0]
            print "Deleting tag for user %s: %s" % (user, tag)
            self.taghandler.del_tag(user, tag)
            return
            
        self.customhandler.detect(status.user.screen_name, text[len(prefix):])
        
class Bot:
    consumer_key='FSWJUlCHsAaiLBDY1MMEA'
    consumer_secret='aCFv6Tslb038cdUAIv7m4QDplBn076wvLd4YKmC3yU'
    
    key = "135845084-FONlvU4wGXyl9o4RkfyPdv4grclbqr4Pi2UH2w3j"
    secret = "DC6I1xp2uONTIYOL2DtEIljhl46LEkUwlPB5NUEBds"
    
    def __init__(self):
        self.auth = tweepy.OAuthHandler(consumer_key = self.consumer_key,
                                        consumer_secret = self.consumer_secret)
        self.auth.set_access_token(self.key, self.secret)
        self.api = tweepy.API(self.auth)
    
    def auth(self):
        try:
            redirect_url = self.auth.get_authorization_url()
        except tweepy.TweepError:
            print 'Error! Failed to get request token.'
            
        verifier = raw_input('Verifier:')

        try:
            self.auth.get_access_token(verifier)
        except tweepy.TweepError:
            print 'Error! Failed to get access token.'
           
        self.key, self.secret = self.auth.access_token.key, self.auth.access_token.secret
        print self.key, self.secret
    
    def stream(self):
        self.botname = self.api.me().screen_name
        print "Bot started: @" + self.botname
        self.taghandler = TagHandler(self.api, self.botname)
        self.customhandler = CustomHandler(self.api)
        self.listener = Listener(self.botname, self.taghandler, self.customhandler)
        self.stream = Stream(self.auth, self.listener)
        self.stream.filter(track=(self.botname, ))
        
if __name__ == "__main__":
    bot = Bot()
    bot.stream()
    

