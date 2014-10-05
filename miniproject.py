#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os, re
import logging
from collections import OrderedDict

import urllib, json, jinja2

import webapp2
from google.appengine.api import urlfetch
from google.appengine.api import users as gusers
from google.appengine.ext import ndb
from google.appengine.api import mail as gmail

from services import *
from models import Stream, User


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

NAV_LINKS = OrderedDict([('Create', '/create')
                         ,('View', '/view')
                         ,('Search', '/search')
                         ,('Trending', '/trending')
                         ,('Social', '/social')
                         ,('Manage', '/manage')])

SERVICES_URL = 'http://localhost:8080'
# SERVICES_URL = 'http://apt-miniproject-fall14.appspot.com/services'
# query_params = {'service': 'getstreams', 'user_id': user_id}
# urllib.urlencode


def CallService(service,**params):
    result = urlfetch.fetch(SERVICES_URL+'/svc_'+service, payload=json.dumps(params), method=urlfetch.POST)

    jresult = json.loads(result.content)

    status = {}
    if 'error' in jresult:
        status['error'] = jresult['error']
    elif not result.status_code == 200:
        status['error'] = "HTTP %d Error" % result.status_code

    if 'status' in jresult:
        status['status'] = jresult['status']
    else:
        status['status'] = "HTTP %d" % result.status_code

    return status, jresult


class ErrorHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {}        
        template_values['nav_links'] = NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()

        template_values['error'] = self.request.get('error')
        
        template = JINJA_ENVIRONMENT.get_template('error.html')
        self.response.write(template.render(template_values))


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.redirect('/login')

    
class LoginHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {}

        user = gusers.get_current_user()
        if user:
            self.redirect('/manage')
            return
        else:
            template_values['url'] = gusers.create_login_url(self.request.uri)
            template_values['url_text'] = "Log In"
            template_values['user_name'] = 'GmailUserID'

        template = JINJA_ENVIRONMENT.get_template('login.html')
        self.response.write(template.render(template_values))


class ManageHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()

        # Create new user account if needed
        cxsuser = User.getUser(gusers.get_current_user().user_id())
        if not cxsuser:
            cxsuser = User(user_id=user.user_id())
            cxsuser.put()

        # Get streams
        status, result = CallService('get_strm',user_id=cxsuser.user_id)
        if 'error' in status:
            self.redirect('/error?'+urllib.urlencode(status))
            return

        template_values['page_title'] = "Streams I own"
        template_values['user_streams'] = result['user_streams']
        template_values['subscribed_streams'] = result['subscribed_streams']

        template = JINJA_ENVIRONMENT.get_template('manage.html')
        self.response.write(template.render(template_values))

    def post(self):
        # Delete any requested streams
        form = {'user_id': gusers.get_current_user().user_id()}
        if self.request.get('delete'):
            svc = 'del_strm'
        if self.request.get('unsubscribe'):
            svc = 'unsub_strm'

        form['streams'] = self.request.get_all('stream_id')
        status, result = CallService(svc,**form)
        if 'error' in status:
            self.redirect('/error?'+urllib.urlencode(status))
            return

        self.redirect('/manage')
        return


class CreateHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()

        template = JINJA_ENVIRONMENT.get_template('create.html')
        self.response.write(template.render(template_values))

    def post(self):
        form = {}

        # Fill form and check it was completed
        for name in ('stream_id','subscribers','tags','cover_url'):
            form[name] = self.request.get(name)

        form['subscribers'] = re.split(r'\s*,?\s*',form['subscribers'].strip())
        form['tags'] = re.split(r'\s#*,?\s*',form['tags'].strip())
        form['user_id'] = gusers.get_current_user().user_id()

        # Request to create a new stream
        status, result = CallService('new_strm',**form)
        if 'error' in status:
            self.redirect('/error?'+urllib.urlencode(status))
            return

        # Send invitation e-mails out
        msg = self.request.get('message')
        # SendEmail(msg,form['subscribers'])

        # We're done with you
        self.redirect('/manage')


#View handler
class ViewHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()

        user = gusers.get_current_user()
        cxsuser = User.getUser(user.user_id())
        stream_id = self.request.get('stream_id')
        page_range = self.request.get('page_range')

        status, result = CallService('view',stream_id=stream_id,page_range=page_range)
        if 'error' in status:
            self.redirect('/error?'+urllib.urlencode(status))
            return
        
        template_values['upload_url'] = blobstore.create_upload_url('/upload')
        template_values['stream'] = result['images']
        template_values['stream_id'] = stream_id

        template = JINJA_ENVIRONMENT.get_template('view.html')
        self.response.write(template.render(template_values))

    def post(self):
        form = {}

        form['stream_id'] = self.request.get('stream_id')        
        if self.request.get('subscribe'):
            svc = 'sub_strm'
            form['user_id'] = gusers.get_current_user().user_id()
            form['streams'] = [form['stream_id']]
        elif self.request.get('next'):
            svc = 'view'
            form['page_range'] = self.request.get('page_range')

        status, result = CallService(svc,**form)
        if 'error' in status:
            self.redirect('/error?'+urllib.urlencode(status))
            return

        self.redirect('/view?'+urllib.urlencode({'page_range':result['page_range'] if 'page_range' in result else ''
                                                 ,'stream_id':form['stream_id']}))
            

def SendEmail(msg,to_list):
    to_addr = self.request.get("friend_email")
    if not gmail.is_email_valid(to_addr):
        return False

    message = gmail.EmailMessage()
    message.sender = user.email()
    message.to = to_addr
    message.body = """
# I've invited you to Example.com!

# To accept this invitation, click the following link,
# or copy and paste the URL into your browser's address
# bar:

# %s
#         """ % generate_invite_link(to_addr)

    message.send()

    return True

        
app = webapp2.WSGIApplication([
    ('/', MainHandler)
    ,('/login', LoginHandler)
    ,('/manage', ManageHandler)
    ,('/view', ViewHandler)
    ,('/create', CreateHandler)
    ,('/error',ErrorHandler)
    ,('/svc_upld',UploadHandler)
    ,('/svc_view',ViewStreamHandler)
    ,('/svc_del_usr', DeleteUserHandler)
    ,('/svc_new_usr', CreateUserHandler)    
    ,('/svc_sub_strm', SubscribeHandler)
    ,('/svc_unsub_strm', UnsubscribeHandler)
    ,('/svc_new_strm', CreateStreamHandler)
    ,('/svc_del_strm', DeleteStreamsHandler)
    ,('/svc_get_strm', GetStreamsHandler)
    ,('/svc_test', TestServiceHandler)
], debug=True)
