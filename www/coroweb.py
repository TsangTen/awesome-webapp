#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Ten Tsang'

import asyncio
import os
import inspect
import logging
import functools
from urllib import parse
from aiohttp import web
from apis import APIError

def get(path):
	'''
		Define decorator @get('/path')
	'''
	def decorator(func):
		@functools.wraps(func)
		# @functools.wraps(func)使得被装饰函数的‘__name__’属性，对应为该函数，而不是‘__wrapper__’
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'GET'  # 添加了属性‘__method__’
		wrapper.__route__ = path  # 添加了属性‘__route__’
		return wrapper
	return decorator

def post(path):
	'''
		Define decorator @post('/path')
	'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'POST'
		wrapper.__route__ = path
		return wrapper
	return decorator

def get_required_kw_args(fn):
	# 获取请求的参数
	args = []
	params = inspect.signature(fn).parameters  # inspect.signature获取fn的所有参数，parameters以映射形式返回
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			# KEYWORD_ONLY指只能通过参数名赋值，empty指参数没有默认值
			args.append(name)
	return tuple(args)

def get_named_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

def has_named_kw_args(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True

def has_var_kw_arg(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True

def has_request_arg(fn):
	sig = inspect.signature(fn)
	params = sig.parameters
	found = False
	for name, param in params.items():
		if name == 'request':
			found = True
			continue
		if found and (
			param.kind != inspect.Parameter.VAR_POSITIONAL 
			and param.kind != inspect.Parameter.KEYWORD_ONLY 
			and param.kind != inspect.Parameter.VAR_KEYWORD
		):
			raise ValueError('request parameter must be named parameter in function: %s%s' % (fn.__name__, str(sig)))
	return found


class RequestHandler(object):
'''
	网络请求处理器（类）
'''
	def __init__(self, app, fn):
		self._app = app
		self._func = fn
		self._has_request_arg = has_request_arg(fn)
		self._has_var_kw_arg = has_var_kw_arg(fn)
		self._has_named_kw_args = get_named_kw_args(fn)
		self._named_kw_args = get_named_kw_args(fn)
		self._required_kw_args = get_required_kw_args(fn)
	
	# @asyncio.coroutine
	# def __call__(self, request):
	# 	kw = ..
	# 	r = yield from self._func(**kw)
	# 	return r
	async def __call__(self, request):
		kw = None
		if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
			if request.method == 'POST':
				if not request.content_type:
					return web.HTTPBadRequest('Missing Content Type.')
				ct = request.content_type.lower()
				if ct.startswith('application/json'):
					params = await request.json()
					if not isinstance(params, dict):
						return web.HTTPBadRequest('JSON body must be object.')
					kw = params
				elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
					params = await request.post()
					kw = dict(**params)
				else:
					return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
			if request.method == 'GET':
				qs = request.query_string
				if qs:
					kw = dict()
					for k, v in parse.parse_qs(qs, True).items():
						kw[k] = v[0]
		if kw is None:
			kw = dict(**request.match_info)
		else:
			if not self._has_var_kw_arg and self._named_kw_args:
				# remove all unamed kw:
				copy = dict()
				for name in self._named_kw_args:
					if name in kw:
						copy[name] = kw[name]
				kw = copy
			# check named arg:
			for k, v in request.match_info.items():
				if k in kw:
					logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
				kw[k] = v
		if self._has_request_arg:
			kw['request'] = request
		# check required kw:
		if self._required_kw_args:
			for name in self._required_kw_args:
				if not name in kw:
					return web.HTTPBadRequest('Missing argument: %s' % name)
		logging.info('call with args: %s' % str(kw))
		try:
			r = await self._func(**kw)
			return r
		except APIError as e:
			return dict(error=e.error, data=e.data, message=e.message)

def add_static(app):
	'''
		用了配置css，js，字体，图片等文件的路径
		param：
			app：aiohttp模块中web.Application生成的对象
	'''
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
	# os.path.join()用于拼接路径
	# os.path.dirname()用于获取文件所在文件夹路径
	# os.path.abspath()用于获取文件所在绝对路径
	# __file__为本文件，这里即coroweb.py
	app.router.add_static('/static/', path)  # 这是aiohttp模块中的add_static
	logging.info('add static %s => %s' % ('/static/', path))

def add_route(app, fn):
	'''
		用来注册一个URL处理函数
		param：
			app：aiohttp模块中web.Application生成的对象
			fn：一个用@get(path)或@post(path)装饰的处理函数，这里是handlers.py中的函数
	'''
	method = getattr(fn, '__method__', None)  # 获取方法，‘GET’或‘POST’
	# 如果fn存在属性'__method__'，则返回属性的值，否则返回None
	path = getattr(fn, '__route__', None)  # 获取路径，即页面路径
	if path is None or method is None:
		raise ValueError('@get or @post not defined in %s.' % str(fn))
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
	# 如果fn不是携程函数（用async def定义的，或用@asyncio.coroutine装饰的函数）
	# The function that defines a coroutine (a function definition using async def 
	# or decorated with @asyncio.coroutine)
	# 且不是生成器函数，则把它变为携程函数
		fn = asyncio.coroutine(fn)
	logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
	app.router.add_route(method, path, RequestHandler(app, fn))  # 这是aiohttp模块中的add_route


# 变成自动扫描：
# 自动把handler模块的所有符合条件的函数注册了
def add_routes(app, module_name):
	n = module_name.rfind('.')  # 查找右边第一个‘.’的位置
	if n == (-1):  # 即没找到‘.’，说明不存在父模块
		mod = __import__(module_name, globals(), locals())  # 直接导入模块
	else:
		name = module_name[n+1:]  # 模块名
		mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)  # 从父模块中导入相应模块
	for attr in dir(mod):  # 遍历模块中所有函数
		if attr.startswith('_'):  # 忽略以‘_’开头的
			continue
		fn = getattr(mod, attr)  # 获取模块中相应属性
		if callable(fn):  # 如果是可调用的（函数）
			method = getattr(fn, '__method__', None)  # 获取方法
			path = getattr(fn, '__route__', None)  # 获取路径
			if method and path:  # 如果存在方法和路径，可以注册一个URL处理函数
				add_route(app, fn)