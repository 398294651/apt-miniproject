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

NAV_LINKS = {'Create': '/create'
             ,'View': '/view'
             ,'Search': '/search'
             ,'Trending': '/trending'
             ,'Social': '/social'
             ,'Manage': '/manage'}

SERVICES_URL = 'http://localhost:8080'
# SERVICES_URL = 'http://apt-miniproject-fall14.appspot.com/services'
# query_params = {'service': 'getstreams', 'user_id': user_id}
# urllib.urlencode


def CallService(service,**params):
    result = urlfetch.fetch(SERVICES_URL+'/svc_'+service, payload=json.dumps(params), method=urlfetch.POST)

    jresult = json.loads(result.content)

    status = {}
    if jresult['error']:
        status['error'] = jresult['error']
    elif not result.status_code == 200:
        status['error'] = "HTTP %d Error" % result.status_code

    if jresult['status']:
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
            # form = json.dumps({'user':user})
            # result = urlfetch.fetch('/manage', payload=form, method=urlfetch.POST)
            self.redirect('/manage')
            return

            # template_values['url'] = gusers.create_logout_url(self.request.uri)
            # template_values['url_text'] = "Log out"
            # template_values['user_name'] = user.nickname()
        else:
            template_values['url'] = gusers.create_login_url(self.request.uri)
            template_values['url_text'] = "Log In"
            template_values['user_name'] = 'GmailUserID'

        template = JINJA_ENVIRONMENT.get_template('login.html')
        self.response.write(template.render(template_values))

    # def post(self):
    #     uid = self.request.get('user_id')
    #     pw = self.request.get('password')

    #     if un and pw:
    #         self.redirect('/manage')
    #     else:
    #         self.redirect('/login')

# Management
class ManageHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()

        user = gusers.get_current_user()
        cxsuser = User.getUser(user.user_id())

        # Create new user account if needed
        user_streams = None
        subscribed_streams = None
        if not cxsuser:
            cxsuser = User(user_id=user.user_id())
            cxsuser.put()
        else:
            status, result = CallService('get_strm',user_id=cxsuser.user_id,service=get_streams)
            if 'error' in status:
                self.redirect('/error?'+urllib.urlencode(status))
                return

            user_streams = result['user_streams']
            subscribed_streams = result['subscribed_streams']

        template_values['page_title'] = "Streams I own"
        template_values['user_streams'] = user_streams
        template_values['subscribed_streams'] = subscribed_streams

        template = JINJA_ENVIRONMENT.get_template('manage.html')
        self.response.write(template.render(template_values))


    def post(self):
        # Delete any requested streams
        if self.request.get('delete'):
            None
        
        # Unsubscribe to any requested streams
        if self.request.get('unsubscribe'):
            None

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

        if not form['stream_id'] or not form['tags']:
            self.redirect('/create')
            return

        form['subscribers'] = re.split(r'\s*,?\s*',form['subscribers'].strip())
        form['tags'] = re.split(r'\s*,?\s*',form['tags'].strip())
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

class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
  def get(self, resource):
    resource = str(urllib.unquote(resource))
    blob_info = blobstore.BlobInfo.get(resource)
    self.send_blob(blob_info)


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
  def post(self):
    upload = self.get_uploads('filename')[0]

    user_photo = Image(image_id=self.request.get('title')
                       ,image_blob=upload.key())

    stream = Stream.getStream(self.request.get('stream_id'))
    stream.images.insert(0,user_photo.image_blob)
    stream.put()

    self.redirect('/view')

class SubscribeHandler(webapp2.RequestHandler):
    def post(self):
        user = User.getUser(self.request.get('user_id'))
        user.subscribed_streams = form['streams'] + user.subscribed_streams
        user.put()


#View handler
class ViewHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()

        user = gusers.get_current_user()
        cxsuser = User.getUser(user.user_id())
        stream_id = self.request.get('stream_id')
        page_range = self.request.get('pg_rg')
        
        status, result = CallService('view',stream_id=stream_id,page_range=page_range)
        if 'error' in status:
            self.redirect('/error?'+urllib.urlencode(status))
            return
        
        template_values['upload_url'] = blobstore.create_upload_url('/upload')
        template_values['stream'] = result['images']

        template = JINJA_ENVIRONMENT.get_template('view.html')
        self.response.write(template.render(template_values))

    def post(self):
        form = {}
        form['user_id'] = gusers.get_current_user().user_id()

        service = 'view_stream'
        lastimg = self.request.get('img3')
        form['page_range'] = range(lastimg+1,lastimg+4)

        status, result = CallService(service,**form)
        if 'error' in status:
            self.redirect('/error?'+urllib.urlencode(status))
            return

        self.redirect('/view')
            

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
    ,('/svc_sub', SubscribeHandler)
    ,('/svc_upld',UploadHandler)
    ,('/svc_view',ViewStreamHandler)
    ,('/svc_del_usr', DeleteUserHandler)
    ,('/svc_new_usr', CreateUserHandler)    
    ,('/svc_new_strm', CreateStreamHandler)
    ,('/svc_del_strm', DeleteStreamsHandler)
    ,('/svc_get_strm', GetStreamsHandler)
    ,('/svc_testsvc', TestServiceHandler)
], debug=True)
