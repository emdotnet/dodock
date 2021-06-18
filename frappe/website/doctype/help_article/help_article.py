# Copyright (c) 2013, Frappe and contributors
# For license information, please see license.txt


import frappe
from frappe.website.website_generator import WebsiteGenerator
from frappe.utils import is_markdown, markdown, cint
from frappe.website.utils import get_comment_list
from frappe import _

class HelpArticle(WebsiteGenerator):
	def validate(self):
		self.set_route()

	def set_route(self):
		'''Set route from category and title if missing'''
		if not self.route:
			self.route = '/'.join([frappe.get_value('Help Category', self.category, 'route'),
				self.scrub(self.title)])

	def on_update(self):
		self.update_category()
		clear_cache()

	def update_category(self):
		cnt = frappe.db.sql("""select count(*) from `tabHelp Article`
			where category=%s and ifnull(published,0)=1""", self.category)[0][0]
		cat = frappe.get_doc("Help Category", self.category)
		cat.help_articles = cnt
		cat.save()

	def get_context(self, context):
		if self.login_required and frappe.session.user=='Guest':
			frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

		if is_markdown(context.content):
			context.content = markdown(context.content)
		context.login_required = True
		context.category = frappe.get_doc('Help Category', self.category)
		context.level_class = get_level_class(self.level)
		context.comment_list = get_comment_list(self.doctype, self.name)
		context.show_sidebar = True
		context.sidebar_items = get_sidebar_items()
		context.parents = self.get_parents(context)

	def get_parents(self, context):
		return [{"title": context.category.category_name, "route":context.category.route}]

def get_list_context(context=None):
	filters = dict(published=1)
	introduction = False

	category = frappe.db.get_value("Help Category", { "route": frappe.local.path }, ["name", "category_description", "login_required"], as_dict=True)

	if category:
		if cint(category.get("login_required")) and frappe.session.user=='Guest':
			frappe.throw(_("You need to be logged in to access this page"), frappe.PermissionError)

		filters['category'] = category.get("name")
		introduction = category.get("category_description")

	if frappe.session.user == "Guest":
		filters['login_required'] = 0

	list_context = frappe._dict(
		title = category.get("name") if category else _("Knowledge Base"),
		get_level_class = get_level_class,
		show_sidebar = True,
		sidebar_items = get_sidebar_items(),
		hide_filters = True,
		filters = filters,
		category = frappe.local.form_dict.category,
		no_breadcrumbs = True,
		introduction=introduction
	)


	if frappe.local.form_dict.txt:
		list_context.blog_subtitle = _('Filtered by "{0}"').format(frappe.local.form_dict.txt)
	#
	# list_context.update(frappe.get_doc("Blog Settings", "Blog Settings").as_dict())
	return list_context

def get_level_class(level):
	return {
		"Beginner": "green",
		"Intermediate": "orange",
		"Expert": "red"
	}[level]

def get_sidebar_items():
	def _get():
		conditions = ""
		if frappe.session.user == "Guest":
			conditions = " and login_required=0"

		return frappe.db.sql("""select
				category_name as title,
				concat('/', route) as route
			from
				`tabHelp Category`
			where
				ifnull(published,0)=1 and help_articles > 0
			{conditions}
			order by
				help_articles desc""".format(conditions=conditions), as_dict=True)

	return frappe.cache().get_value("knowledge_base:category_sidebar", _get)

def clear_cache():
	clear_website_cache()

	from frappe.website.utils import clear_cache
	clear_cache()

def clear_website_cache(path=None):
	frappe.cache().delete_value("knowledge_base:category_sidebar")
	frappe.cache().delete_value("knowledge_base:faq")

@frappe.whitelist(allow_guest=True)
def add_feedback(article, helpful):
	field = "helpful"
	if helpful == "No":
		field = "not_helpful"

	value = cint(frappe.db.get_value("Help Article", article, field))
	frappe.db.set_value("Help Article", article, field, value+1, update_modified=False)