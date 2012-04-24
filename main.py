# -*- coding:utf-8 -*-
#!/usr/bin/env python
#
# Copyright 2010 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
A barebones AppEngine application that uses Facebook for login.
Make sure you add a copy of facebook.py (from python-sdk/src/) into this
directory so it can be imported.
"""

FACEBOOK_APP_ID = '380301575348408'
FACEBOOK_APP_SECRET = '0eda44fd6207fb3eec4dc8fef298c8c1'

RESTAURANT_ID = {
	'000': 'waraukado',
	'001': 'salvatore',
	'010': 'filo',
	'011': 'ribs',
	'100': 'yosyushonin',
	'101': 'goku',
	'110': 'tomoe',
	'111': 'shomoto'
}

import ConfigParser

conf = ConfigParser.SafeConfigParser()
conf.read( 'restaurant.ini' )

import facebook
import os.path
import wsgiref.handlers
import logging
import urllib2

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template
from google.appengine.api.urlfetch import fetch

import sys
stdin = sys.stdin
stdout = sys.stdout
reload(sys)
sys.setdefaultencoding( 'utf-8' )
sys.stdin = stdin
sys.stdout = stdout

def gf_getBrowser( auser_agent ) :
	lv_user_agent = auser_agent.lower()
	ln_ret = lv_user_agent.find( 'iphone' )
	if ln_ret != -1 :
		return 1
	ln_ret = lv_user_agent.find( 'android' )
	if ln_ret != -1 :
		return 1
	return 0

class User( db.Model ) :
    id = db.StringProperty( required = True )
    created = db.DateTimeProperty( auto_now_add = True )
    updated = db.DateTimeProperty( auto_now = True )
    name = db.StringProperty( required = True )
    profile_url = db.StringProperty( required = True )
    access_token = db.StringProperty( required = True )


class BaseHandler( webapp.RequestHandler ) :
    """Provides access to the active Facebook user in self.current_user

    The property is lazy-loaded on first access, using the cookie saved
    by the Facebook JavaScript SDK to determine the user ID of the active
    user. See http://developers.facebook.com/docs/authentication/ for
    more information.
    """
    @property
    def current_user( self ) :
        if not hasattr( self, '_current_user' ) :
            self._current_user = None
            cookie = facebook.get_user_from_cookie(
            	self.request.cookies,
            	FACEBOOK_APP_ID,
            	FACEBOOK_APP_SECRET
            )
            if cookie :
                # Store a local instance of the user data so we don't need
                # a round-trip to Facebook on every request
                user = User.get_by_key_name( cookie['uid'] )
                if not user :
                    graph = facebook.GraphAPI( cookie['access_token'] )
                    profile = graph.get_object( 'me' )
                    user = User(
                    	key_name = str( profile['id'] ),
                    	id = str( profile['id'] ),
                    	name = profile['name'],
                    	profile_url = profile['link'],
                    	access_token = cookie['access_token']
                    )
                    user.put()
                elif user.access_token != cookie['access_token'] :
                    user.access_token = cookie['access_token']
                    user.put()
                self._current_user = user
        return self._current_user

class HomeHandler( BaseHandler ) :
    def get( self ) :
        path = os.path.join( os.path.dirname( __file__ ), 'index.html' )
        args = dict(
        	current_user = self.current_user,
        	facebook_app_id = FACEBOOK_APP_ID,
        	ua_check = gf_getBrowser( self.request.user_agent )
        )
        self.response.out.write( template.render( path, args ) )

    def post( self ) :
        self.get()

class ResultHandler( BaseHandler ) :
    def get( self ) :
        if self.request.get( 'check' ) :
        	user = self.current_user
        	q1 = self.request.get( 'q1' )
        	q2 = self.request.get( 'q2' )
        	result_id = q1 + q2 + str( int( user.id ) % 2 )
        	restaurant_id =  RESTAURANT_ID[result_id]
        	message = '%s %s さんは、武蔵小山の「%s」との相性が抜群との診断結果が出ました。近いうちに常連になりそうな予報が出ています。いや、もうすでに常連になっているかも!?　皆さんも試してみませんか？' % ( conf.get( restaurant_id, 'prepend' ).encode( 'utf-8' ), user.name.encode( 'utf-8' ), conf.get( restaurant_id, 'name' ).encode( 'utf-8' ) )
        	name = '武蔵小山の飲食店との相性診断'
        	link = 'https://apps.facebook.com/musako_affinity_test/'
        	caption = 'レストラン相性診断アプリ'
        	description = '診断結果は「%s」（%s／%s）でした。' % ( conf.get( restaurant_id, 'name' ).encode( 'utf-8' ), conf.get( restaurant_id, 'address' ).encode( 'utf-8' ), conf.get( restaurant_id, 'phone' ).encode( 'utf-8' ) )
        	img_src = 'http://musako201204.appspot.com/%s.jpg' % ( restaurant_id )
        	attachment = {
            	'name': name,
            	'link': link,
            	'caption': caption,
            	'description': description,
            	'picture': img_src
            }
        	graph = facebook.GraphAPI( user.access_token )
        	graph.put_wall_post( message, attachment )
        	path = os.path.join( os.path.dirname( __file__ ), 'result.html' )
        	args = dict(
				current_user = user,
				restaurant = {
					'id': restaurant_id,
					'name': conf.get( restaurant_id, 'name' )
				},
        		facebook_app_id = FACEBOOK_APP_ID,
				ua_check = gf_getBrowser( self.request.user_agent )
			)
        	self.response.out.write( template.render( path, args ) )
        else :
            self.redirect( '/' )

    def post( self ) :
        self.get()

class DetailHandler( BaseHandler ) :
    def get( self, restaurant_id ) :
		path = os.path.join( os.path.dirname( __file__ ), 'detail.html' )
		args = dict(
			name = conf.get( restaurant_id, 'name' ),
			category = conf.get( restaurant_id, 'category' ),
			url = conf.get( restaurant_id, 'url' ),
			address = conf.get( restaurant_id, 'address' ),
			phone = conf.get( restaurant_id, 'phone' ),
			hours = conf.get( restaurant_id, 'hours' ),
			closed = conf.get( restaurant_id, 'closed' )
		)
		self.response.out.write( template.render( path, args ) )

class MapHandler( BaseHandler ) :
    def get( self, restaurant_id ) :
		path = os.path.join( os.path.dirname( __file__ ), 'map.html' )
		args = dict(
			name = conf.get( restaurant_id, 'name' ),
			latlng = conf.get( restaurant_id, 'latlng' ),
			address = conf.get( restaurant_id, 'address' )
		)
		self.response.out.write( template.render( path, args ) )

class MessageHandler( BaseHandler ) :
    def get( self, restaurant_id ) :
		path = os.path.join( os.path.dirname( __file__ ), 'message.html' )
		args = dict(
			message = conf.get( restaurant_id, 'message' )
		)
		self.response.out.write( template.render( path, args ) )

def main() :
    logging.getLogger().setLevel( logging.DEBUG )
    routes = [
    	( r'/', HomeHandler ),
    	( r'/result', ResultHandler ),
    	( r'/detail/(.*?)', DetailHandler ),
    	( r'/map/(.*?)', MapHandler ),
    	( r'/message/(.*?)', MessageHandler )
    ]
    util.run_wsgi_app( webapp.WSGIApplication( routes ) )


if __name__ == '__main__' :
    main()
