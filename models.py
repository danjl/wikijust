#their modules
from google.appengine.ext import db
from google.appengine.api import memcache
import logging
#my modules
import utils
import cPickle
import datetime

class User(db.Model):
    username = db.StringProperty(required=True)
    password = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)

    def cache(self):
#        memcache.add(self.key().id(), cPickle.dumps(self))
         s = cPickle.dumps(self)
         memcache.add(self.username, s)
         return s


    @classmethod
    def from_cache(cls, key):
        """Can take user_id or username"""
        s = memcache.get(key)
        if s:
            return cPickle.loads(s)

    @classmethod
    def new_user(cls, username, password):
        u = cls.by_name(username)
        if not u:
            pw_hash = utils.hashs(password)
            u = cls(username = username, password = pw_hash)
            logging.debug("CACHING USER: " + u.username)

            #if the cache is successfull, write to db
            #may prevent some concurrency issues
            if u.cache():
                u.put()
                return u
        else:
            raise utils.UsernameTaken("Username already taken.")

    @classmethod
    def by_name(cls, username, cache=True):
        """ Checks the cache for username, if none found, it checks the db

        :param username: the username to search for
        :return u: an instance of user that matched the username
        """
        u = None
        if cache:
            u = cls.from_cache(username)
        if not u or not cache:
#            u = db.GqlQuery('SELECT * FROM User WHERE username = :1 LIMIT 1', username) 
            u = db.GqlQuery('SELECT * FROM User WHERE username = :1 LIMIT 1', username) 
            logging.debug("USER BY NAME DB QUERY. USERNAME=" + username )
            try:
                return u[0]
            except IndexError:
                pass
        else:
            return u
 
    def check_password(self, password):
        salt = self.password[-6:]
        new_hash = utils.hashs(password, salt)
        if new_hash == self.password:
            return True
        else:
            return False


    @classmethod
    def login(cls, username, password):
        u = cls.by_name(username, cache=False) 
        if u:
           if u.check_password(password):
               return u
           else:
               raise utils.PasswordError("Wrong Password.")
            
        else:
           raise utils.UsernameError("Username not found.")
               


class Session(db.Model):
    user_id = db.IntegerProperty(required=True)
    username = db.StringProperty(required=True)
    session_id = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    expires = db.DateTimeProperty()

    """
    @classmethod
    def __init__(cls):
        cls.update_expires()
        session_id = utils.make_salt(25)
        cls.session_id = session_id
        memcache.add(session_id, cls.key().id())
        logging.debug("NEW SESSION DB WRITE")
        memcache.add(cls.session_id, cls.user_id)
    """

    def cache(self):
        s = cPickle.dumps(self)
        memcache.add(self.session_id, s) 
        return s
    
    @classmethod
    def from_cache(cls, session_id):
        s = memcache.get(session_id)
        if s:
            try:
                return cPickle.loads(s)
            except TypeError:
                return None


    @classmethod
    def update_expires(cls, days=14):
        cls.expires = cls.expires = datetime.date.today() + datetime.timedelta(days)
        logging.debug("UPDATE SESSION EXPIRES DB WRITE")
        return cls.expires

    @classmethod
    def reset_session_id(cls):
        memcache.delete(cls.session_id)
        session_id = cls.new_session()
        memcache.add(session_id, cls.user_id)
        cls.session_id = session_id
        return cls.session_id

    @classmethod
    def new_session(cls, user_id, username):
        session_id = utils.make_salt(25)
        s = cls(session_id=session_id, user_id=user_id, username=username)
        #if the cache is successfull, write to db
        #may prevent some concurrency issues
        if s.cache():
            s.put() 
            logging.debug("NEW SESSION DB WRITE")
            return s

    @classmethod
    def get_user_from_session(cls, session_id):
        if session_id is not None:
            session = cls.from_cache(session_id)
            if session:
                return session.username
            else:
                q = db.GqlQuery('SELECT * FROM Session WHERE session_id = :1', session_id)
                logging.debug("DB READ")
                try:
                    session = q[0]
                    session.cache()
                    return session.username
                except IndexError:
                    pass

class Page(db.Model):
    # TODO Remove the stuff I'm not usering anymore.
    title = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
#    edited = db.DateTimeProperty(auto_now=True)
    created_by = db.StringProperty(required=True)
    edited_by = db.StringProperty(required=True)
    revision =  db.IntegerProperty(required=True)

    def cache(self):
        s = cPickle.dumps(self)
        memcache.add(self.title, s)
        return s
    
    def cache_newest_revision(self):
        memcache.set("newest " + self.title, self.revision + 1)

    @classmethod
    def from_cache(cls, title, revision):
        s = memcache.get(title + "|" + revision)
        if s:
            return cPickle.loads(s)

    @classmethod
    def get_all_pages(cls, cache = True):
        cache = memcache.get("cache_all")
        l = None 
        if cache == "True":
            l = memcache.get("all_pages")
            if l:
                if type(l) is str:
                    page_list = cPickle.loads(l)
                else:
                    page_list = l
                return page_list
        if cache == "False" or not l:
            q = db.GqlQuery("SELECT * FROM Page ORDER BY created DESC")
            page_list = []
            for p in q:
                if p.title not in page_list:
                    page_list.append( p.title)
            if len(page_list) > 0:
                memcache.set("all_pages", cPickle.dumps(page_list))
                memcache.set("cache_all", "True")
            return page_list

                
    @classmethod
    def update_all_cache(cls, page_title):
        l = memcache.get("all_pages")
        if l:
            if type(l) is str:
                l = cPickle.loads(l)
            l.insert(-1, page_title)
            memcache.set("all_pages", cPickle.dumps(l))
        else:
            l = [page_title]
            memcache.add("all_pages", cPickle.dumps(l))

    @classmethod
    def new_revision(cls, title, content, username, new = False):
        prev_newest = Page.get_newest(title)
        if prev_newest:
            revision = prev_newest.revision + 1
        else:
            revision = 0
        #if this a new page with no previous revisions
        if revision == 0:
            w = cls(title=title, content=content, created_by=username, edited_by=username, revision=revision)
#            cls.update_all_cache(title)
        else:
            w = cls(title=title, content=content, created_by=prev_newest.created_by, edited_by=username, revision=revision)


        w.cache()
        logging.debug("NEW WIKIPAGE DB WRITE")
        memcache.set("cache_all", "False")
        memcache.set("cache_" + title, "False")
        w.put()
#        w.cache_newest_revision()
        
        return w

    @classmethod
    def get(cls, title, revision, cache=True):
        p = memcache.get(title + "|")
        if p:
            return cPickle.loads(p)
        else:
            q = db.GqlQuery('SELECT * FROM Page WHERE title = :1 AND revision = :2', title, revision)
            logging.debug("GET SPECIFIC TITLE AND REVISION DB READ")
            try:
                return q[0]
            except IndexError:
                logging.debug("TITLE :1 REVISION :2, NOT FOUND IN DB OR MEMCACHE", title, revision)


    @classmethod
    def get_newest(cls, title, cache=True):
        """returns the newest revision of a given page."""
        newest_revision = memcache.get("newest " + title)
        if newest_revision:
            p = memcache.get(title + "|" + str(newest_revision))
        else:
            p = None

        if p:
            return cPickle.loads(p)
        else:
            q = db.GqlQuery('SELECT * FROM Page WHERE title = :1 ORDER BY revision DESC LIMIT 1', title)
            logging.debug("GET NEWEST REVISION DB READ")
            try:
                newest = q[0]
                memcache.set("newest " + title, newest.revision)
                return newest
            except IndexError:
                pass


    @classmethod
    def all_by_title(cls, title):
        pages = None
        cache = memcache.get("cache_" + title)
        if cache == "True":
            pages = cPickle.loads(memcache.get("all_" + title))
        if not pages or cache == "False":
           logging.debug("DB READ FOR HISTORY PAGE: " + title)
           pages = db.GqlQuery('SELECT * FROM Page WHERE title = :1 ORDER BY revision DESC', title)
           memcache.set("all_" + title, cPickle.dumps(pages))
           memcache.set("cache_" + title, "True")
        return pages


    @classmethod
    def by_title(cls, title, cache=True):
        """DEPRECIATED
        Get newest revision of a page with a given title
        :param title: The title to search for.
        :param cache: wether or not to check memcache.
        :return s: the newest page object with the given title
        """
        s = None
        if cache:
            s = cls.from_cache(title)
            if s:
                return s
        if not s or not cache:
            try:
                s = db.GqlQuery('SELECT * FROM Page WHERE title = :1 ORDER BY revision DESC LIMIT 1', title)
                return s[0]
            except IndexError:
                return None



