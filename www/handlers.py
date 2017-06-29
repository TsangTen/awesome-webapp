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
from aiohttp import web

import markdown2
from coroweb import get, post
from apis import APIValueError, APIResourceNotFoundError, APIError, Page,APIPermissionError
from models import User, Comment, Blog, next_id
from config import configs

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

def check_admin(request):  # 确认权限
	if request.__user__ is None or not request.__user__.admin:  # 未登录或非管理员
		raise APIPermissionError()  # 返回权限错误

def get_page_index(page_str):  # 获取页面索引
	p = 1
	try:  # 尝试转为整型值
		p = int(page_str)
	except ValueError as e:
		pass
	if p < 1: # 如果小于1，则为1
		p = 1
	return p

# 计算加密cookie
def user2cookie(user, max_age):
	'''
		Generate cookie str by user.
	'''
	# build cookie string by: id-expires-sha1
	expires = str(int(time.time() + max_age))  # cookie过期时间
	s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)  # 格式化cookie串
	L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L)

def text2html(text):
	# map()函数接收两个参数，一个是函数，一个是Iterable，
	# map将传入的函数依次作用到序列的每个元素，并把结果作为新的Iterator返回。
	# filter()函数接收一个函数 f 和一个list，
	# 这个函数 f 的作用是对每个元素进行判断，
	# 返回 True或 False，
	# filter()根据判断结果自动过滤掉不符合条件的元素，
	# 返回由符合条件元素组成的新list。
	lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
	return ''.join(lines)

# 解密cookie
async def cookie2user(cookie_str):
	'''
		Parse cookie and load user if cookie is valid
	'''
	if not cookie_str:  # 不存在cookie
		return None
	try:
		L = cookie_str.split('-')
		if len(L) != 3:  # 此处参考上面user2cookie封装cookie的格式
			return None
		uid, expires, sha1 = L
		if int(expires) < time.time():  # cookie过期
			return None
		user = await User.find(uid)  # 查找用户信息
		if user is None:
			return None
		s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():  # 比对用户信息是否准确
			logging.info('invalid sha1')
			return None
		user.passwd = '******'  # 密码不可视
		return user
	except Exception as e:
		logging.exception(e)
		return None


# @get('/')
# async def index(request):
# 	users = await User.findAll()
# 	return {
# 		'__template__': 'test.html',
# 		'users': users
# 	}

@get('/')
async def index(request):  # 访问主页
	summary = 'Lorem ipsum dolor amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut lobore et dolore magna aliqua.'
	# blogs = [
	# 	Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
	# 	Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
	# 	Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
	# ]
	blogs = await Blog.findAll()  # 获取所有博客
	return {
		'__template__': 'blogs.html',
		'blogs': blogs
	}

@get('/blog/{id}')
async def get_blog(id):  # 访问某篇博客
	blog = await Blog.find(id)  # 通过ID在数据库里查找博客
	comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')  # 获取评论
	for c in comments:  # 输出评论
		c.html_content = text2html(c.content)
	blog.html_content = markdown2.markdown(blog.content)  # 转换博客内容为网页格式
	return {
		'__template__': 'blog.html',
		'blog': blog,
		'comments': comments
	}

@get('/api/users')
async def api_get_users(*, page='1'):  # 查看用户信息
	page_index = get_page_index(page)
	num = await User.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, users=())
	users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	for u in users:
		u.password = '******'
	return dict(page=p, users=users)

@get('/register')
def register():  # 注册页面
	return {
		'__template__': 'register.html'
	}

@get('/signin')
def signin():  # 登录页面
	return {
		'__template__': 'signin.html'
	}

@get('/signout')
def signout(request):  # 登出页面
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME, '-delete-', max_age=0, httponly=True)
	logging.info('user signed out.')
	return r

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@post('/api/users')
async def api_register_user(*, email, name, passwd):  # 注册过程
	if not name or not name.strip():
		raise APIValueError('name', 'Invalid name.')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email', 'Invalid email.')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd', 'Invalid password.')
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

@post('/api/authenticate')
async def authenticate(*, email, passwd):  # 登录认证过程
	if not email:
		raise APIValueError('email', 'Invalid email.')
	if not passwd:
		raise APIValueError('passwd', 'Invalid password')
	users = await User.findAll('email=?', [email])
	if len(users) == 0:
		raise APIValueError('email', 'Email not exist.')
	user = users[0]
	# check passwd:
	sha1 = hashlib.sha1()
	sha1.update(user.id.encode('utf-8'))
	sha1.update(b':')
	sha1.update(passwd.encode('utf-8'))
	if user.passwd != sha1.hexdigest():
		raise APIValueError('passwd', 'Invalid password.')
	# authenticate ok, set cookie:
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r

@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):  # 创建博客
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError('name', 'name cannot be empty.')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty.')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty.')
	blog = Blog(
			user_id=request.__user__.id, 
			user_name=request.__user__.name, 
			user_image=request.__user__.image,
			name=name.strip(),
			summary=summary.strip(),
			content=content.strip()
		)
	await blog.save()
	return blog

@post('/api/blogs/{id}')
async def api_update_blog(id, request, *, name, summary, content):  # 更新博客
	check_admin(request)
	blog = await Blog.find(id)
	if not name or not name.strip():
		raise APIValueError('name', 'name cannot be empty.')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty.')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty.')
	blog.name = name.strip()
	blog.summary = summary.strip()
	blog.content = content.strip()
	await blog.update()
	return blog

@post('/api/blogs/{id}/delete')
async def api_delete_blog(request, *, id):  # 删除博客
	check_admin(request)
	blog = await Blog.find(id)
	await blog.remove()
	return dict(id=id)

@get('/api/blogs')
async def api_blogs(*, page='1'):  # 查看博客
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, blogs=())
	blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, blogs=blogs)

@get('/api/blogs/{id}')
async def api_get_blog(*, id):  # 查看某篇博客
	blog = await Blog.find(id)
	return blog

@get('/manage/')
def manage():  # 管理
	return 'redirect:/manage/comments'

@get('/manage/comments')
def manage_comments(*, page='1'):  # 管理评论
	return {
		'__template__': 'manage_comments.html',
		'page_index': get_page_index(page)
	}

@get('/manage/blogs')
def manage_blogs(*, page='1'):  # 管理博客
	return {
		'__template__': 'manage_blogs.html',
		'page_index': get_page_index(page)
	}

@get('/manage/blogs/create')
def manage_create_blog():  # 管理博客创建
	return {
		'__template__': 'manage_blog_edit.html',
		'id': '',
		'action': '/api/blogs'
	}

@get('/manage/blogs/edit')
def manage_edit_blog(*, id):  # 管理博客编辑
	return {
		'__template__': 'manage_blog_edit.html',
		'id': id,
		'action': '/api/blogs/%s' % id
	}

@get('/api/comments')
async def api_comments(*, page='1'):  # 查看评论
	page_index = get_page_index(page)
	num = await Comment.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, comments=())
	comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, comments=comments)

@get('/api/blogs/{id}/comments')  # 查看某篇博客的评论
async def api_create_comment(id, request, *, content):
	user = request.__user__
	if user is None:
		raise APIPermissionError('Please signin first.')
	if not content or not content.strip():
		raise APIValueError('content', 'empty!')
	blog = await Blog.find(id)
	if blog is None:
		raise APIResourceNotFoundError('Blog')
	comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
	await comment.save()
	return comment

@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):  # 删除某条评论
	check_admin(request)
	c = await Comment.find(id)
	if c is None:
		raise APIResourceNotFoundError('Comment', 'Not Found!')
	await c.remove()
	return dict(id=id)



