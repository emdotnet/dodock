# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
from bs4 import BeautifulSoup
from frappe.utils import cint

def get_jenv():
	import frappe
	from frappe.utils.safe_exec import get_safe_globals

	if not getattr(frappe.local, 'jenv', None):
		from jinja2 import DebugUndefined
		from jinja2.sandbox import SandboxedEnvironment

		# frappe will be loaded last, so app templates will get precedence
		jenv = SandboxedEnvironment(loader = get_jloader(),
			undefined=DebugUndefined)
		set_filters(jenv)

		jenv.globals.update(get_safe_globals())
		jenv.globals.update(get_jenv_customization('methods'))

		frappe.local.jenv = jenv

	return frappe.local.jenv

def get_template(path):
	return get_jenv().get_template(path)

def get_email_from_template(name, args):
	from jinja2 import TemplateNotFound

	args = args or {}
	try:
		message = get_template('templates/emails/' + name + '.html').render(args)
	except TemplateNotFound as e:
		raise e

	try:
		text_content = get_template('templates/emails/' + name + '.txt').render(args)
	except TemplateNotFound:
		text_content = None

	return (message, text_content)

def validate_template(html):
	"""Throws exception if there is a syntax error in the Jinja Template"""
	import frappe
	from jinja2 import TemplateSyntaxError

	jenv = get_jenv()
	try:
		jenv.from_string(html)
	except TemplateSyntaxError as e:
		frappe.msgprint('Line {}: {}'.format(e.lineno, e.message))
		frappe.throw(frappe._("Syntax error in template"))

def render_template(template, context, is_path=None, safe_render=True):
	'''Render a template using Jinja

	:param template: path or HTML containing the jinja template
	:param context: dict of properties to pass to the template
	:param is_path: (optional) assert that the `template` parameter is a path
	:param safe_render: (optional) prevent server side scripting via jinja templating
	'''

	from frappe import get_traceback, throw
	from jinja2 import TemplateError

	if not template:
		return ""

	# if it ends with .html then its a freaking path, not html
	if (is_path
		or template.startswith("templates/")
		or (template.endswith('.html') and '\n' not in template)):
		return get_jenv().get_template(template).render(context)
	else:
		if safe_render and ".__" in template:
			throw("Illegal template")
		try:
			template = transform_template_blot(template, context)

			return get_jenv().from_string(template).render(context)
		except TemplateError:
			throw(title="Jinja Template Error", msg="<pre>{template}</pre><pre>{tb}</pre>".format(template=template, tb=get_traceback()))

def get_jloader():
	import frappe
	if not getattr(frappe.local, 'jloader', None):
		from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

		if frappe.local.flags.in_setup_help:
			apps = ['frappe']
		else:
			apps = frappe.get_hooks('template_apps')
			if not apps:
				apps = frappe.local.flags.web_pages_apps or frappe.get_installed_apps(sort=True)
				apps.reverse()

		if not "frappe" in apps:
			apps.append('frappe')

		frappe.local.jloader = ChoiceLoader(
			# search for something like app/templates/...
			[PrefixLoader(dict(
				(app, PackageLoader(app, ".")) for app in apps
			))]

			# search for something like templates/...
			+ [PackageLoader(app, ".") for app in apps]
		)

	return frappe.local.jloader

def set_filters(jenv):
	import frappe
	from frappe.utils import global_date_format, cint, cstr, flt, markdown
	from frappe.website.utils import get_shade, abs_url

	jenv.filters["global_date_format"] = global_date_format
	jenv.filters["markdown"] = markdown
	jenv.filters["json"] = frappe.as_json
	jenv.filters["get_shade"] = get_shade
	jenv.filters["len"] = len
	jenv.filters["int"] = cint
	jenv.filters["str"] = cstr
	jenv.filters["flt"] = flt
	jenv.filters["abs_url"] = abs_url

	if frappe.flags.in_setup_help:
		return

	jenv.filters.update(get_jenv_customization('filters'))

def transform_template_blot(template, context):
	import frappe
	soup = BeautifulSoup(template, "html.parser")
	soup.insert(0, '{%- from "templates/letters/standard_macros.html" import render_table -%}')
	soup.insert(0, "{% " + " set doc_values = frappe.get_doc('{0}', '{1}') ".format(context.get('doctype'), context.get('name')) + " %}")
	fields = soup.find_all('template-blot')

	if not fields:
		return template

	doctypes = []

	for f in fields:
		new_tag = soup.new_tag("span")

		if f.get('data-doctype') == "Custom Functions" and f.get('data-function') != "null":
			content = "{{" + "{0}|safe".format(f.get('data-function').split('#', 1)[-1]) + "}}"
			if f.get('data-function').startswith("Signature"):
				content = soup.new_tag("img", src=content, height=200, width=200)
				new_tag.append(content)
			else:
				new_tag.string = content
		
		else:
			if f.get('data-doctype') != "Custom Functions" and {f.get('data-doctype'): f.get('data-reference')} not in doctypes \
				and f.get('data-reference') != "name":
				doctypes.append({f.get('data-doctype'): f.get('data-reference')})

			new_tag.string = "{{ " + "{0}|safe".format(get_newtag_string(f, context)) + " }}"

		f.replace_with(new_tag)

	for doctype in doctypes:
		for key in doctype:
			get_doc = "{% " + " set {0} = frappe.get_doc('{1}', {2}) if {2} else None".format(key.replace(" ", "").lower(), key, \
				'doc.{0}'.format(doctype[key]) if 'doc' in context else doctype[key]) + " %}"
			soup.insert(0, get_doc)

	for method in frappe.get_hooks('jinja_template_extensions'):
		soup = frappe.get_attr(method)(soup)

	return soup.prettify()

def get_newtag_string(field, context):
	docname = None

	if (field.get('data-reference') == "name" and "doc" in context) or field.get('data-reference') != "name":
		docname = field['data-doctype'].replace(" ", "").lower()

	if field.get('data-fieldtype') == "Table":
		value = "render_table({0}.meta.get_field('{1}').as_dict(), {0})".format(docname or 'doc_values', field.get('data-value'))
	else:
		if docname:
			value = "{0}.{1} or ''".format(docname, field.get('data-value'))
		else:
			value = "{0} or ''".format(field.get('data-value'))

		if field['data-function'] != "null":
			value = "{0}({1})".format(field.get('data-function'), value)

	return value

def get_jenv_customization(customization_type):
	'''Returns a dict with filter/method name as key and definition as value'''

	import frappe

	out = {}
	if not getattr(frappe.local, "site", None):
		return out

	values = frappe.get_hooks("jenv", {}).get(customization_type)
	if not values:
		return out

	for value in values:
		fn_name, fn_string = value.split(":")
		out[fn_name] = frappe.get_attr(fn_string)

	return out