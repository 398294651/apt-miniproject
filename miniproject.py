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
from datetime import datetime, timedelta
from collections import OrderedDict
from operator import itemgetter

import urllib, json, jinja2

import webapp2
from google.appengine.api import urlfetch
from google.appengine.api import users as gusers
from google.appengine.ext import ndb
from google.appengine.api import mail as gmail
from google.appengine.ext import blobstore

from services import *
from models import Stream, User

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

NAV_LINKS = sorted(('Create', 'View', 'Search', 'Trending', 'Manage'))
NAV_LINKS = OrderedDict(zip(NAV_LINKS, map(lambda x: '/'+x.lower(), NAV_LINKS) ))
USER_NAV_LINKS = NAV_LINKS.copy()

SERVICES_URL = 'http://localhost:8080'
TIME_FMT = "%Y-%m-%d %H:%M:%S.%f"
# SERVICES_URL = 'http://apt-miniproject-fall14.appspot.com/'


def format_timesince(value,fmt=TIME_FMT):
    tl = datetime.now() - datetime.strptime(value,fmt)
    hours, remainder = divmod(tl.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "{0:02d}:{1:02d}:{2:02d}".format(hours,minutes,seconds)

JINJA_ENVIRONMENT.filters['timesince'] = format_timesince
logging.getLogger().setLevel(logging.DEBUG)


class HTTPRequestHandler(webapp2.RequestHandler):
    @staticmethod
    def callService(category,service,**params):
        result = urlfetch.fetch('/'.join((SERVICES_URL,'svc',category,service))
                                , payload=json.dumps(params), method=urlfetch.POST)

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

    def render(self,src,**form):
        template = JINJA_ENVIRONMENT.get_template(src)
        self.response.write(template.render(form))

    def redirect(self,url,params=None):
        params = ('?'+urllib.urlencode(params)) if params else ''
        url += params
        super(HTTPRequestHandler,self).redirect(url)

    def sendEmail(self, user_id, msg, to_list):
        message = gmail.EmailMessage()
        message.sender = "toemossgarcia@gmail.com"
        message.to = to_list
        message.subject = "[Connex.us] User %s has shared their stream with you!" % user_id
        message.body = msg
        message.body += """
      
    # To accept this invitation, click the following link,
    # or copy and paste the URL into your browser's address
    # bar:

    # %s
    #         """ % "www.google.com"

        message.send()


class ErrorHandler(HTTPRequestHandler):
    def get(self):
        template_values = {}        
        template_values['nav_links'] = USER_NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()
        template_values['error'] = self.request.get('error')

        self.render('error.html',**template_values)


class LoginHandler(HTTPRequestHandler):
    def get(self):
        self.render('login.html',user_id="GmailUserID")

    def post(self):
        user = User.getUser(self.request.get('user_id'))
        if not user:
            logging.error("User does not exist.")
            return self.redirect('/login')            
        elif self.request.get('user_pw') != user.user_pw:
            logging.error("Bad password.")
            return self.redirect('/login')

        for key,link in NAV_LINKS.items():
            USER_NAV_LINKS[key] = link+'?'+urllib.urlencode({'user_id':user.user_id})

        self.redirect('/manage',{'user_id':user.user_id})

# Options for dealing with mobile+browser clients:
#       pass in a function for rendering
#       no function? return json
#       may want to expose json returning interfaces for mobile use
class ManageHandler(HTTPRequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = USER_NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()
        template_values['user_id'] = self.request.get('user_id')

        # Get streams
        status, result = self.callService('stream','get',user_id=self.request.get('user_id'))
        if 'error' in status: return self.redirect('/error',status)

        template_values['user_streams'] = result['user_streams']
        template_values['subscribed_streams'] = result['subscribed_streams']

        self.render('manage.html',**template_values)

    def post(self):
        form = {'user_id': self.request.get('user_id')}
        form['streams'] = self.request.get_all('stream_id')

        if self.request.get('delete'):      svc = 'del'
        if self.request.get('unsubscribe'): svc = 'unsub'
        status, result = self.callService('stream',svc,**form)
        if 'error' in status: return self.redirect('/error',status)

        return self.redirect('/manage',{'user_id':self.request.get('user_id')})


class CreateHandler(HTTPRequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = USER_NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()
        template_values['user_id'] = self.request.get('user_id')

        self.render('create.html',**template_values)

    def post(self):
        form = {}

        # Fill form and check it was completed
        for name in ('stream_id','subscribers','tags','cover_url'):
            form[name] = self.request.get(name)

        form['subscribers'] = re.findall(r',?\s*([\w\.@]+)\s*,?',form['subscribers'])
        form['tags'] = re.findall(r',?\s*#(\w+)\s*,?',form['tags'])
        form['user_id'] = self.request.get('user_id')
        if not all(map(gmail.is_email_valid,form['subscribers'])):
            return self.redirect('/create',{'user_id':form['user_id']})

        # Request to create a new stream
        status, result = self.callService('stream','new',**form)
        if 'error' in status: return self.redirect('/error',status)

        # Send invitation e-mails out
        msg = self.request.get('message')
        if form['subscribers']:
            self.sendEmail(form['user_id'],msg,form['subscribers'])

        # We're done with you
        self.redirect('/manage',{'user_id':form['user_id']})


class ViewAllHandler(HTTPRequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = USER_NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()
        template_values['user_id'] = self.request.get('user_id')
        
        status, result = self.callService('stream','viewall')
        if 'error' in status: return self.redirect('/error',status)

        template_values['streams'] = result['streams']
        self.render('viewall.html',**template_values)


class TrendingHandler(HTTPRequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = USER_NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()
        template_values['user_id'] = self.request.get('user_id')

        status, result = self.callService('stream','viewall')
        if 'error' in status: return self.redirect('/error',status)
        streams = sorted(result['streams'],key=lambda x: len(x['views']),reverse=True)[:3]
        template_values['streams'] = streams

        status, result = self.callService('report','getrate')
        if 'error' in status: return self.redirect('/error',status)

        rate = result['rate']
        template_values['checked'] = None
        checked = [""] * 4
        if result['rate']:
            if rate == "0":         idx = 0
            elif rate == "5":       idx = 1
            elif rate == "60":      idx = 2        
            elif rate == "1440":    idx = 3
        else:
            idx = 0
        checked[idx] = "checked=checked"
        template_values['checked'] = checked

        self.render('trending.html',**template_values)        

    def post(self):
        rate = self.request.get('rate')
        # update cron job rate
        status, result = self.callService('report','setrate',rate=rate)
        if 'error' in status: return self.redirect('/error',status)

        self.redirect('/trending',{'user_id':self.request.get('user_id')})


class ViewHandler(HTTPRequestHandler):
    def get(self):
        template_values = {}
        template_values['nav_links'] = USER_NAV_LINKS
        template_values['path'] = os.path.basename(self.request.path).capitalize()
        template_values['user_id'] = self.request.get('user_id')        

        stream_id = self.request.get('stream_id')
        page_range = self.request.get('page_range')
        if not page_range: page_range = '0,1,2'
        if '/manage' in self.request.referer or '/trending' in self.request.referer:
            status, result = self.callService('stream','addview',stream_id=stream_id)
            if 'error' in status: return self.redirect('/error',status)

        status, result = self.callService('stream','view'
                                          ,stream_id=stream_id,page_range=page_range)
        if 'error' in status: return self.redirect('/error',status)

        redirect = '/svc/img/upload?'+urllib.urlencode({'stream_id':stream_id})
        template_values['upload_url'] = blobstore.create_upload_url(redirect)
        template_values['stream'] = result['images']
        template_values['stream_id'] = stream_id
        template_values['page_range'] = page_range

        self.render('viewstream.html',**template_values)

    def post(self):
        form = {}
        form['stream_id'] = self.request.get('stream_id')        
        form['user_id'] = self.request.get('user_id')

        if self.request.get('subscribe'):
            svc = 'sub'
            form['streams'] = [form['stream_id']]
        elif self.request.get('next'):
            svc = 'view'
            form['page_range'] = ','.join(str(int(i)+1) for i in self.request.get('page_range').split(','))

        status, result = self.callService('stream',svc,**form)
        if 'error' in status: return self.redirect('/error',status)

        ret = {'stream_id':form['stream_id'],'user_id':form['user_id']}
        if self.request.get('next'):
            if len(result['page_range']) < len(form['page_range'].split(',')):
                ret['page_range'] = '0,1,2'
            else:
                ret['page_range'] = ','.join(map(str,result['page_range']))

        self.redirect('/viewstream',ret)
            

app = webapp2.WSGIApplication([
    ('/', LoginHandler)
    ,('/login', LoginHandler)
    ,('/manage', ManageHandler)
    ,('/viewstream', ViewHandler)
    ,('/view', ViewAllHandler)
    ,('/create', CreateHandler)
    ,('/error',ErrorHandler)
    ,('/trending',TrendingHandler)
    ,('/svc/img/upload',UploadHandler)
    ,('/svc/img/serve',ServeHandler)
    ,('/svc/user/del', DeleteUserHandler)
    ,('/svc/user/new', CreateUserHandler)    
    ,('/svc/stream/viewall',ViewAllStreamsHandler)
    ,('/svc/stream/view',ViewStreamHandler)
    ,('/svc/stream/sub', SubscribeStreamsHandler)
    ,('/svc/stream/unsub', UnsubscribeStreamsHandler)
    ,('/svc/stream/new', CreateStreamHandler)
    ,('/svc/stream/del', DeleteStreamsHandler)
    ,('/svc/stream/get', GetStreamsHandler)
    ,('/svc/stream/addview', AddViewHandler)
    ,('/svc/report/getrate', GetReportRateHandler)
    ,('/svc/report/setrate', SetReportRateHandler)
    ,('/svc/report/send', SendReportHandler)
    ,('/svc/test', TestServiceHandler)
], debug=True)

# best practice for user passing - use cookies
# but can also by user forms
