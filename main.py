import os
import sys
sys.path.append(os.path.dirname(__file__) + "lib/markdown")
import markdown
import utils
import webapp2
import logging
from lxml.html.clean import Cleaner
from lxml.html.clean import autolink_html
from jinja2 import Environment, FileSystemLoader
from models import User
from models import Session
from models import Page

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(loader = FileSystemLoader(template_dir), autoescape=True)


class BaseHandler(webapp2.RequestHandler):
    def render_str(self, template, **kw):
        t = env.get_template(template)
        return t.render(kw)

    def write(self, string):
        self.response.out.write(string)

    def render(self, template, page_titles=None, **kw):
        if not page_titles:
            page_titles = Page.get_all_pages()
        self.write(self.render_str(template, page_titles=page_titles, **kw))

    def new_session_cookie(self, session_id):
        self.response.headers.add_header("set-cookie", "session_id=" + session_id)

    def authenticate_session_id(self):
        cookies = self.request.cookies
        if cookies.has_key('session_id'):
            username = Session.get_user_from_session(cookies['session_id'])
            if username:
                return User.by_name(username)
         


class Signup(BaseHandler):
    def get(self):
        self.render('signup.html')
    
    def post(self):
        username = self.request.get("username")
        password = self.request.get("password")
        verify = self.request.get("verify") 
        error = ""
        if password != verify:
            error += "Passwords do not match. <br />"
        if not utils.validate_uname(username):
            error += "Invalid username. <br/>"
        if not utils.validate_pw(password):
            error += "Invalid password. <br/>"

        if error is "":
            try:
                u = User.new_user(username, password)
                logging.debug("NEW USER DB WRITE. USERNAME: " + username)
                s = Session.new_session(user_id=u.key().id(), username=u.username)
                logging.debug("NEW SESSION DB WRITE. SESSION_ID: " + s.session_id)
                self.new_session_cookie(s.session_id)
                self.redirect("/welcome")
            except utils.UsernameTaken, e:
                error += "Username already taken."
                self.render("signup.html", error=error)
        else:
            self.render("signup.html", error=error)

class Login(BaseHandler):
    def get(self):
        self.render("login.html")

    def post(self):
        username = self.request.get("username")
        password = self.request.get("password")
        error = ""

        try:
            u = User.login(username, password)
        except utils.PasswordError:
            error += "Wrong Password. <br />"
        except utils.UsernameError:
            error += "Username not found. <br />"

        if error == "":
            s = Session.new_session(u.key().id(), u.username)
            self.new_session_cookie(s.session_id)
            self.redirect("/welcome")
        else:
            self.render("login.html", error=error)


class Logout(BaseHandler):
    def get(self):
        user = self.authenticate_session_id()
        if user:
            self.response.headers.add_header("set-cookie", "session_id=''")
            self.redirect("/")
        else:
            self.redirect("/login")


class EditPage(BaseHandler):
    def get(self, page_title, revision=None):
        page_title = page_title.strip('/')
        user = self.authenticate_session_id()

        if not user:
            self.redirect("/login")
        elif revision is None:
            p = Page.get_newest(page_title)
            if p:
                self.render("edit.html", user=user.username, title=p.title, content=p.content)
        elif revision == "/new" or revision == "new":
            self.render("edit.html", user=user.username, title=page_title)
        else:
            revision = int(revision.strip('/'))
            p = Page.get(page_title, revision)
            self.render("edit.html", user=user.username, title=page_title, content=p.content)
   
    def post(self, page_title, revision=None):
        user = self.authenticate_session_id()
        page_title = page_title.strip('/')
        content = self.request.get("content")
#        content = autolink_html(content)
#        cleaner = Cleaner(remove_tags=["p", "div"])
#        content = cleaner.clean_html(content)
        Page.new_revision(page_title, content, user.username)
        self.redirect("/" + page_title)


class WikiPage(BaseHandler):
    def get(self, page_title, revision=None):
        user = self.authenticate_session_id()

        #remove slash at beginning
        page_title = page_title.strip('/')

        if revision is None:
            p = Page.get_newest(page_title)
        else:
            #change to int
            revision = int(revision.strip('/'))
            p = Page.get(page_title, revision)

        if p:
            md = markdown.Markdown(safe_mode='escape', output_format='html5', extensions=['attr_list', 'fenced_code', 'codehilite'])
            content = md.convert(p.content)
            if user:
                self.render("wikipage.html", user=user.username, content=content, title=p.title, creator=p.created_by, last_editor=p.edited_by, version=p.revision)
            else:
                self.render("wikipage.html", content=content, title=p.title, creator=p.created_by, last_editor=p.edited_by, version=p.revision)
        else:
            self.redirect("/_edit/" + page_title + "/new")

        """
        w = Page.by_title(page_title)
        if w:
            self.render("wikipage.html", user=user.username, content=w.content, title=w.title, creator=w.created_by, last_editor=w.edited_by)
        else:
            self.redirect("/_edit/" + page_title)

        """

class Welcome(BaseHandler):
    def get(self):
        user = self.authenticate_session_id()
        if user:
            self.render("welcome.html", user =user.username)
        else:
            self.write("User not found.")


class Home(BaseHandler):
    def get(self):
        user = self.authenticate_session_id()
        pages = Page.get_all_pages()
        if user:
            self.render("home.html", user=user.username, pages=pages, page_titles=pages)
        else:
            self.render("home.html", pages=pages, page_titles=pages)

class History(BaseHandler):
    def get(self, page_title):
        user = self.authenticate_session_id()
        page_title = page_title.strip('/')
        pages = Page.all_by_title(page_title)
        if user:
            self.render("history.html", user=user.username, title=page_title, pages=pages)
        else:
            self.render("history.html", title=page_title, pages=pages)



logging.getLogger().setLevel(logging.DEBUG)
PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'
NUMBER_RE = r'(/[0-9]+|new)'
app = webapp2.WSGIApplication([('/signup', Signup),
                               ('/login', Login),
                               ('/welcome', Welcome),
                               ('/logout', Logout),
                               ('/', Home),
                               ('/_history' + PAGE_RE, History),
                               ('/_edit' + PAGE_RE + NUMBER_RE, EditPage),
                               ('/_edit' + PAGE_RE, EditPage),
                               (PAGE_RE + NUMBER_RE, WikiPage),
                               (PAGE_RE, WikiPage),
                               ],
                               debug=True)
