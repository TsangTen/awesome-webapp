#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Ten Tsang'

import logging; logging.basicConfig(level=logging.INFO)
import asyncio
import os
import json
import time
from datetime import datetime
from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static
from handlers import cookie2user, COOKIE_NAME
from config import configs



def init_jinja2(app, **kw):
	logging.info('init jinja2...')
	options = dict(
		autoescape = kw.get('autoescape', True),
		block_start_string = kw.get('block_start_string', '{%'),
		block_end_string = kw.get('block_end_string', '%}'),
		variable_start_string = kw.get('variable_start_string', '{{'),
		variable_end_string = kw.get('variable_end_string', '}}'),
		auto_reload = kw.get('auto_reload', True)
	)  # options中的各个key是Environment的模板参数，用于定义模板格式
	# Help on built-in function get:
	#	get(...)
    #	D.get(k[,d]) -> D[k] if k in D, else d.  d defaults to None.
	path = kw.get('path', None)
	if path is None:  # 如果路径为空，则将根目录下的templates文件夹作为路径
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
	logging.info('set jinja2 template path: %s' % path)
	env = Environment(loader=FileSystemLoader(path), **options)  # 载入模板路径及模板格式
	filters = kw.get('filters', None)
	if filters is not None:
		for name, f in filters.items():
			env.filters[name] = f  # 配置过滤器，这里是博客发布时间
	app['__templating__'] = env

async def logger_factory(app, handler):  # 在处理网络请求前，打印请求方法和路径日志
	async def logger(request):
		logging.info('Request: %s %s' % (request.method, request.path))
		# await asyncio.sleep(0.3)
		return (await handler(request))
	return logger

async def auth_factory(app, handler):  # 在处理网络请求前，确认是否已登录
	async def auth(request):
		logging.info('check user: %s %s' % (request.method, request.path))
		request.__user__ = None
		cookie_str = request.cookies.get(COOKIE_NAME)
		if cookie_str:  # 如果有cookies数据
			user = await cookie2user(cookie_str)  # 尝试获取用户名
			if user:  # 如果用户名存在
				logging.info('set current user: %s' % user.email)
				request.__user__ = user
		if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
			return web.HTTPFound('/signin')  # 跳转到登录页面
		return (await handler(request))
	return auth

async def data_factory(app, handler):  # 在处理网络请求前，判断数据内容类型
	async def parse_data(request):
		if request.method == 'POST':
			if request.content_type.startswith('application/json'):
				request.__data__ = await request.json()
				logging.info('request json: %s' % str(request.__data__))
			elif request.content_type.startswith('application/x-www-form-urlencoded'):
				request.__data__ = await request.post()
				logging.info('request form: %s' % str(request.__data__))
		return (await handler(request))
	return parse_data

async def response_factory(app, handler):  # 在处理网络请求后，对回复内容进行确认
	async def response(request):
		logging.info('Response handler...')
		r = await handler(request)  # 处理网络请求
		if isinstance(r, web.StreamResponse):  # 此情况下，直接回复
			return r
		if isinstance(r, bytes):  # 如果处理结果是“字节”
			resp = web.Response(body=r)  # 转换类型
			resp.content_type = 'application/octect-stream'  # 标记内容类型
			return resp
		if isinstance(r, str):  # 如果处理结果是“字符串”
			if r.startswith('redirect'):  # 如果头部存在此字符串
				return web.HTTPFound(r[9:])  # 忽略字符串“redirect”
			resp = web.Response(body=r.encode('utf-8'))  # 转换类型，以utf-8编码
			resp.content_type = 'text/html;charset=utf-8'
			return resp
		if isinstance(r, dict):  # 如果处理结果是“字典（即映射）”
			template = r.get('__template__')  # 获取当前页面
			if template is None:  # 如果页面不存在
				# 转换类型
				resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o:o.__dict__).encode('utf-8'))
				resp.content_type = 'application/json;charset=utf-8'
				return resp
			else:  # 页面存在
				r['__user__'] = request.__user__  # 用户信息
				# 渲染页面
				resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
				resp.content_type = 'text/html;charset=utf-8'
				return resp
		if isinstance(r, int) and r >= 100 and r < 600:
			return web.Response(r)
		if isinstance(r, tuple) and len(r) == 2:
			t, m = r
			if isinstance(t, int) and t >= 100 and t < 600:
				return web.ReferenceError(t, str(m))
		# default
		resp = web.Response(body=str(r).encode('utf-8'))
		resp.content_type = 'text/plain;charset=utf-8'
		return resp
	return response

def datetime_filter(t):  # 文章创建日期
	delta = int(time.time() - t)
	if delta < 60:
		return u'1分钟前'
	if delta < 3600:
		return u'%s分钟前' % (delta // 60)
	if delta < 86400:
		return u'%s小时前' % (delta // 3600)
	if delta < 604800:
		return u'%s天前' % (delta // 86400)
	dt = datetime.fromtimestamp(t)
	return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

'''
def index(request):
	return web.Response(body=b'<h1>Awesome</h1>', content_type='text/html')

@asyncio.coroutine
def init(loop):
	app = web.Application(loop=loop)
	app.router.add_route('Get', '/', index)
	srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
	logging.info('server started at http://127.0.0.1:9000...')
	return srv
'''
async def init(loop):
	# await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='root', password='1qazxsw2', db='awesome')
	await orm.create_pool(loop=loop, **configs.db)
	app = web.Application(loop=loop, middlewares=[  # 类似于Python的装饰器，在handler执行前后执行
		logger_factory, auth_factory, response_factory
	])
	init_jinja2(app, filters=dict(datetime=datetime_filter))  # 初始化jinja2环境
	add_routes(app, 'handlers')  # 对网络请求进行处理
	add_static(app)  # 导入css，js，img，字体等
	srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)  # 创建服务器
	logging.info('server started at http://127.0.0.1:9000...')
	return srv


# 为了从同步代码中调用一个协同程序，我们需要一个事件循环
loop = asyncio.get_event_loop()  # 得到一个标准的事件循环
loop.run_until_complete(init(loop))  # 运行协同程序
# Run until the Future is done.
# If the argument is a coroutine object, it is wrapped by ensure_future().
# Return the Future’s result, or raise its exception.
loop.run_forever()
# Run until stop() is called. 
# If stop() is called before run_forever() is called, 
# this polls the I/O selector once with a timeout of zero, 
#　runs all callbacks scheduled in response to I/O events 
# (and those that were already scheduled), 
# and then exits. 
# If stop() is called while run_forever() is running, 
# this will run the current batch of callbacks and then exit. 
# Note that callbacks scheduled by callbacks will not run in that case; 
# they will run the next time run_forever() is called.

