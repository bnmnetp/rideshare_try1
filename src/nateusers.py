#!/usr/bin/env python
import os, glob, os.path, codecs, logging, cgi, urllib, urllib2
from datetime import datetime

import base64
import Cookie
import email.utils
import hashlib
import hmac
import time
import wsgiref.handlers
import facebook

from django.utils import simplejson as json
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import users
from google.appengine.ext.db import Key
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.api import memcache
from myutil import *
#from model import Recipe, FBUser
#from recipe_dissect import ParsedRecipe
#
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

#FACEBOOK_APP_ID = "193298730706524"  # for localhost testing
#FACEBOOK_APP_ID = "206075606121536" # for beta site
FACEBOOK_APP_ID = "284196238289386"  # for live site

#FACEBOOK_APP_SECRET = "44d7cce20524dc91bf7694376aff9e1d" # for localhost
#FACEBOOK_APP_SECRET = "2c4151f8959ea75522b49ea6ccbb1469" # for beta
FACEBOOK_APP_SECRET = "07e3ea3ffda4aa08f8c597bccd218e75"  # for live site

userId= None
logging.getLogger().setLevel(logging.DEBUG)

class User():

    def __init__(self):
      self.user = FBUser.get_by_key_name(userId)
    
    def nickname(self):
      return self.user.name
  
def create_logout_url(token):
    return '/auth/logout'
        
def create_login_url():
    return '/auth/login'

class FBUser(db.Model):
    id = db.StringProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)
    name = db.StringProperty(required=True)
    profile_url = db.StringProperty(required=True)
    access_token = db.StringProperty(required=True)
    email = db.EmailProperty()
    drivercomments = db.StringListProperty()
    public_link = db.StringProperty()
    rating = db.FloatProperty()
    numrates= db.IntegerProperty(default=0)
    


    def nickname(self):
       return self.name
  
def get_current_user():
    return User()

class BaseHandler(webapp.RequestHandler):
    @property
    def current_user(self):
        """Returns the logged in Facebook user, or None if unconnected."""
        if not hasattr(self, "_current_user"):
            self._current_user = None
            user_id = parse_cookie(self.request.cookies.get("fb_user"))
            if user_id:
                self._current_user = FBUser.get_by_key_name(user_id)
        return self._current_user

    def create_context(self):
        cd = {}

        if self.current_user:
            cd['nickname'] = self.current_user.name
            cd['public_link'] = self.current_user.public_link
            cd['logout_url'] = "/auth/logout"
            cd['isuser'] = True
        else:
            cd['login_url'] = "/auth/login"
            cd['isuser'] = False
        return cd


def parse_cookie(value):
    """Parses and verifies a cookie value from set_cookie"""
    if not value: return None
    parts = value.split("|")
    if len(parts) != 3: return None
    if cookie_signature(parts[0], parts[1]) != parts[2]:
        logging.warning("Invalid cookie signature %r", value)
        return None
    timestamp = int(parts[1])
    if timestamp < time.time() - 30 * 86400:
        logging.warning("Expired cookie %r", value)
        return None
    try:
        return base64.b64decode(parts[0]).strip()
    except:
        return None


def cookie_signature(*parts):
    """Generates a cookie signature.

    We use the Facebook app secret since it is different for every app (so
    people using this example don't accidentally all use the same secret).
    """
    hash = hmac.new(FACEBOOK_APP_SECRET, digestmod=hashlib.sha1)
    for part in parts: hash.update(part)
    return hash.hexdigest()


def set_cookie(response, name, value, domain=None, path="/", expires=None):
    """Generates and signs a cookie for the give name/value"""
    timestamp = str(int(time.time()))
    value = base64.b64encode(value)
    signature = cookie_signature(value, timestamp)
    cookie = Cookie.BaseCookie()
    cookie[name] = "|".join([value, timestamp, signature])
    cookie[name]["path"] = path
    if domain: cookie[name]["domain"] = domain
    if expires:
        cookie[name]["expires"] = email.utils.formatdate(
            expires, localtime=False, usegmt=True)
    response.headers._headers.append(("Set-Cookie", cookie.output()[12:]))


class LoginHandler(BaseHandler):
    def get(self):
        """

        """
        verification_code = self.request.get("code")
        nexthop = self.request.get('lasthop')
        args = dict(client_id=FACEBOOK_APP_ID, redirect_uri=self.request.path_url)
        if self.request.get("code"):
            args["client_secret"] = FACEBOOK_APP_SECRET
            args["code"] = self.request.get("code")
            response = cgi.parse_qs(urllib2.urlopen(
                "https://graph.facebook.com/oauth/access_token?" +
                urllib.urlencode(args)).read())
            access_token = response["access_token"][-1]
   

            # Download the user profile and cache a local instance of the
            # basic profile info
            profile = json.load(urllib2.urlopen(
                "https://graph.facebook.com/me?" +
                urllib.urlencode(dict(access_token=access_token))))
            schoolList = []
            if 'education' in profile.keys():
                for item in profile["education"]:
                    schoolList.append(item["school"]["name"])
                logging.debug("profile = " + str(profile))
                if "Luther College" in schoolList:
                    user = FBUser.get_by_key_name(profile["id"])
                    if not user:
                        logging.debug("User not found:  id = " + str(profile["id"]))
                        user = FBUser(key_name=str(profile["id"]), id=str(profile["id"]),
                                      name=profile["name"], access_token=access_token,
                                      profile_url=profile["link"],public_link=profile["id"])
                        user.put()
                    else:
                        user.access_token=access_token
                        user.put()

                    set_cookie(self.response, "fb_user", str(profile["id"]),
                               expires=time.time() + 30 * 86400)
                    self.redirect("/")
                else:
                    self.redirect("/school")
            else:
                self.redirect("/school")
        else:
            args["scope"] = "publish_stream,email,offline_access,manage_pages"
            self.redirect(
                "https://graph.facebook.com/oauth/authorize?" +
                urllib.urlencode(args))


class LogoutHandler(BaseHandler):
    def get(self):
        set_cookie(self.response, "fb_user", "", expires=time.time() - 86400)
        self.redirect("/signout")

