#coding:utf-8
from tweepy.streaming import StreamListener, Stream
import sqlite3, re
import memcache

class MemCache:
    def __enter__(self):
        self.mc = memcache.Client(['unix:/tmp/memcached.sock'], debug=0)
        return self.mc
    def __exit__(self, type, value, traceback):
        self.mc.disconnect_all()

class TagHandler:
    nums = u"① ② ③ ④ ⑤ ⑥ ⑦ ⑧ ⑨ ⑩"
    nums = nums.split()
    
    def __init__(self, api):
        self.db = sqlite3.connect("bot.db")
        self.c = self.db.cursor()
        self.api = api
        try:
            self.c.execute("CREATE TABLE tags(user str, tags str, commenters str)")
        except sqlite3.OperationalError:
            pass
            
    def get_nick(self, user):
        with MemCache() as mc:
            key = user.encode("utf-8")
            nick = mc.get(key)
            if nick:
                return nick
            else:
                try:
                    a = self.api.get_user(user)
                    a = a.name
                except:
                    a = ""
            nick = a
            mc.set(key, nick, time = 86400)
        return nick
    
    def tweet(self, text):
        print "Tweet: " + text,
        try:
            self.api.update_status(text)
            print "Success"
        except:
            print "Failed"
            
    def save_tag(self, user, tag, commenter):
        self.c.execute("SELECT tags, commenters FROM tags WHERE user = ?", (user, ))
        l = self.c.fetchone()
        if l == None:
            self.c.execute("INSERT INTO tags(user, tags, commenters) VALUES(?,?,?)",
                           (user, tag, commenter))
            params = dict(
                            replyto = commenter,
                            user = user,
                            tag = tag,
                            nick = self.get_nick(user)
                        )
            tweetstr = u"@%(replyto)s 给【%(nick)s @%(user)s】添加Tag:%(tag)s 成功了喵>.<" % params
        else:
            tags = l[0].split(",")
            commenters = l[1].split(",")
            
            goon = True
            if commenter in commenters:
                print "User already Tagged this target, ignoring"
                params = dict(
                            replyto = commenter,
                            user = user,
                            tag = tag,
                            nick = self.get_nick(user)
                         )
                tweetstr = u"@%(replyto)s 乃已经给【%(nick)s @%(user)s】添加过Tag啦!" % params
                goon = False
                
            if goon and tag in tags:
                print "Tag already exists, ignoring"
                params = dict(
                            replyto = commenter,
                            user = user,
                            tag = tag,
                            nick = self.get_nick(user)
                         )
                tweetstr = u"@%(replyto)s 【%(nick)s @%(user)s】已经有这个Tag:%(tag)s 啦>.<" % params
                goon = False
            
            if goon:
                tags.append(tag)
                
                if len(tags) > 10:
                    tags.remove(tags[0])
                
                newtags = ",".join(tags)
                commenters.append(commenter)
                newcommenters = ",".join(commenters)
                self.c.execute("UPDATE tags SET tags = ?, commenters = ? WHERE user = ?",
                               (newtags, newcommenters, user))
                params = dict(
                            replyto = commenter,
                            user = user,
                            tag = tag,
                            nick = self.get_nick(user)
                         )
                tweetstr = u"@%(replyto)s 给【%(nick)s @%(user)s】添加Tag:%(tag)s 成功了喵>.<" % params
                
        self.db.commit()
        self.tweet(tweetstr)
    
    def get_tag(self, user, replyto):
        self.c.execute("SELECT tags FROM tags WHERE user = ?", (user, ))
        l = self.c.fetchone()
        if l is None:
            params = dict(
                            replyto = replyto,
                            user = user,
                            nick = self.get_nick(user)
                         )
            tweetstr = u"@%(replyto)s %(nick)s @%(user)s 还没有Tag哦! 发送 \"@o68 %(user)s 您想添加的Tag\" 立刻给Ta添加Tag吧!" % params
            
        else:
            tags = l[0].split(",")
            tags = "".join(["".join(x) for x in zip(self.nums[:len(tags)], tags)])
            params = dict(
                            replyto = replyto,
                            user = user,
                            tag = tag,
                            nick = self.get_nick(user)
                         )
            tweetstr = u"@%(replyto)s 【%(nick)s @%(user)s】的推特Tag:%(tags)s" % params
        
        self.tweet(tweetstr)

class Listener(StreamListener):
    rsettag = re.compile("^@[oO]68 ([a-zA-Z0-9_-]+) ([^\s]+)$")
    rgettag = re.compile("^@[oO]68 ([a-zA-Z0-9_-]+)$")
    
    def __init__(self, taghandler):
        StreamListener.__init__(self)
        self.taghandler = taghandler
    
    def on_status(self, status):
        text = status.text.strip()
        replyto = status.user.screen_name
        print "Original tweet:", replyto, ":", text
        
        settag = self.rsettag.findall(text)
        if len(settag):
            user, tag = settag[0]
            print "Setting tag for user %s: %s" % (user, tag)
            self.taghandler.save_tag(user, tag, replyto)
            
        gettag = self.rgettag.findall(text)
        if len(gettag):
            user = gettag[0]
            print "Getting tag for user %s" % (user, )
            self.taghandler.get_tag(user, replyto)

if __name__ == "__main__":
    import tweepy
    
    consumer_key='FSWJUlCHsAaiLBDY1MMEA'
    consumer_secret='aCFv6Tslb038cdUAIv7m4QDplBn076wvLd4YKmC3yU'
    
    key = "135845084-FONlvU4wGXyl9o4RkfyPdv4grclbqr4Pi2UH2w3j"
    secret = "DC6I1xp2uONTIYOL2DtEIljhl46LEkUwlPB5NUEBds"
    
    auth = tweepy.OAuthHandler(consumer_key = consumer_key,
                               consumer_secret = consumer_secret)
    # Uncomment when you want to authorize a new bot
    
    #try:
    #    redirect_url = auth.get_authorization_url()
    #except tweepy.TweepError:
    #    print 'Error! Failed to get request token.'

    #print redirect_url
    #verifier = raw_input('Verifier:')

    #try:
    #    auth.get_access_token(verifier)
    #except tweepy.TweepError:
    #    print 'Error! Failed to get access token.'
        
    #key, secret = auth.access_token.key, auth.access_token.secret
    #print key, secret
    
    auth.set_access_token(key, secret)
    api = tweepy.API(auth)
    
    taghandler = TagHandler(api)
            
    listener = Listener(taghandler)
    stream = Stream(auth, listener)
    stream.filter(track=("o68", ))

