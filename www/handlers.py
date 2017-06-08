#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Ten Tsang'

' url handlers '

import re
import time
import json
import logging
import hashlib
import base64
import asyncio

from coroweb import get, post
from models import User, Comment, Blog, next_id

# @get('/')
# async def index(request):
# 	users = await User.findAll()
# 	return {
# 		'__template__': 'test.html',
# 		'users': users
# 	}

@get('/')
async def index(request):
	summary = 'Lorem ipsum dolor amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut lobore et dolore magna aliqua.'
	blogs = [
		Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
		Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
		Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
	]
	return {
		'__template__': 'blogs.html',
		'blogs': blogs
	}

# @get('/api/users')
# async def api_get_users():
# 	users = await User.findAll(orderBy='created_at desc')
# 	for u in users:
# 		u.password = '******'
# 	return dict(users=users)

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@post('/api/users')
async def api_register_user(*, email, name, passwd):
	if not name or not name.strip():
		raise APIValueError('name')
	if not email or _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd')
	users = await User.findAll('email=?', [email])
	if len(users) > 0:
		raise APIError('register: failed', 'email', 'Email is already in use.')
	uid = next_id()
	sha1_passwd = '%s:%s' % (uid, passwd)
	user = User(
			id=uid, 
			name=name.strip(), 
			email=email, 
			passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
			image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest()
		)
	await user.save()
	# make session cookie:
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r