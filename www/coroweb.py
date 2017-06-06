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
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = ' GET'
		wrapper.__route__ = path
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
		wrapper.__method__ = ' POST'
		wrapper.__route__ = path
		return wrapper
	return decorator

def get_required_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
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

	def __init__(self, app, fn):
		self._app = app
		self._func = fn
	
	@asyncio.coroutine
	def __call__(self, request):
		kw = ..
		r = yield from self._func(**kw)
		return r


def add_route(app, fn):
	'''
	用来注册一个URL处理函数
	'''
	method = getattr(fn, '__method__', None)
	path = getattr(fn, '__route__', None)
	if path is None or method is None:
		raise ValueError('@get or @post not defined in %s.' % str(fn))
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		fn = asyncio.coroutine(fn)
	logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
	app.router.add_route(method, path, RequestHandler(app, fn))


# 变成自动扫描：
# 自动把handler模块的所有符合条件的函数注册了
def add_routes(app, module_name):
	n = module_name.rfind('.')
	if n = (-1):
		mod = __import__(module_name, globals(), locals())
	else:
		name = module_name[n+1:]
		mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
	for attr in dir(mod):
		if attr.startswith('_'):
			continue
		fn = getattr(mod, attr)
		if callable(fn):
			method = getattr(fn, '__method__', None)
			path = getattr(fn, '__route__', None)
			if method and path:
				add_route(app, fn)