// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import Desktop from './components/Desktop.vue';

frappe.provide('frappe.views.pageview');
frappe.provide("frappe.standard_pages");

frappe.views.pageview = {
	with_page: function(name, callback) {
		if(in_list(Object.keys(frappe.standard_pages), name)) {
			if(!frappe.pages[name]) {
				frappe.standard_pages[name]();
			}
			callback();
			return;
		}

		if((locals.Page && locals.Page[name] && locals.Page[name].script) || name==window.page_name) {
			// already loaded
			callback();
		} else if(localStorage["_page:" + name] && frappe.boot.developer_mode!=1) {
			// cached in local storage
			frappe.model.sync(JSON.parse(localStorage["_page:" + name]));
			callback();
		} else {
			// get fresh
			return frappe.call({
				method: 'frappe.desk.desk_page.getpage',
				args: {'name':name },
				callback: function(r) {
					if(!r.docs._dynamic_page) {
						localStorage["_page:" + name] = JSON.stringify(r.docs);
					}
					callback();
				},
				freeze: true,
			});
		}
	},
	show: function(name) {
		if(!name) {
			name = (frappe.boot ? frappe.boot.home_page : window.page_name);

			if(name === "desktop") {
				if(!frappe.pages.desktop) {
					let page = frappe.container.add_page('desktop');
					let container = $('<div class="container"></div>').appendTo(page);
					container = $('<div></div>').appendTo(container);

					Vue.prototype.__ = window.__;
					Vue.prototype.frappe = window.frappe;

					new Vue({
						el: container[0],
						render: h => h(Desktop)
					});
				}

				frappe.container.change_to('desktop');
				frappe.utils.set_title(__('Home'));
				return;
			}
		}
		frappe.model.with_doctype("Page", function() {
			frappe.views.pageview.with_page(name, function(r) {
				if(r && r.exc) {
					if(!r['403'])
						frappe.show_not_found(name);
				} else if(!frappe.pages[name]) {
					new frappe.views.Page(name);
				}
				frappe.container.change_to(name);
			});
		});
	}
};

frappe.views.Page = Class.extend({
	init: function(name) {
		this.name = name;
		var me = this;
		// web home page
		if(name==window.page_name) {
			this.wrapper = document.getElementById('page-' + name);
			this.wrapper.label = document.title || window.page_name;
			this.wrapper.page_name = window.page_name;
			frappe.pages[window.page_name] = this.wrapper;
		} else {
			this.pagedoc = locals.Page[this.name];
			if(!this.pagedoc) {
				frappe.show_not_found(name);
				return;
			}
			this.wrapper = frappe.container.add_page(this.name);
			this.wrapper.label = this.pagedoc.title || this.pagedoc.name;
			this.wrapper.page_name = this.pagedoc.name;

			// set content, script and style
			if(this.pagedoc.content)
				this.wrapper.innerHTML = this.pagedoc.content;
			frappe.dom.eval(this.pagedoc.__script || this.pagedoc.script || '');
			frappe.dom.set_style(this.pagedoc.style || '');
		}

		this.trigger_page_event('on_page_load');
		// set events
		$(this.wrapper).on('show', function() {
			window.cur_frm = null;
			me.trigger_page_event('on_page_show');
			me.trigger_page_event('refresh');
		});
	},
	trigger_page_event: function(eventname) {
		var me = this;
		if(me.wrapper[eventname]) {
			me.wrapper[eventname](me.wrapper);
		}
	}
});

const notFoundIcons = ["not_found.svg", "404.svg", "empty.svg", "taken.svg", "no_data.svg"]
const notPermittedIcons = ["security.svg", "safe.svg", "vault.svg", "secure_data.svg"]

let notFound = notFoundIcons[Math.floor(Math.random() * notFoundIcons.length)];
let notPermitted = notPermittedIcons[Math.floor(Math.random() * notPermittedIcons.length)];

frappe.show_not_found = function(page_name) {
	frappe.show_message_page({
		page_name: page_name,
		message: __("Sorry! I could not find what you were looking for."),
		img: `/assets/frappe/images/ui/${notFound}`
	});
};

frappe.show_not_permitted = function(page_name) {
	frappe.show_message_page({
		page_name: page_name,
		message: __("Sorry! You are not permitted to view this page."),
		img: `/assets/frappe/images/ui/${notPermitted}`,
		// icon: "octicon octicon-circle-slash"
	});
};

frappe.show_message_page = function(opts) {
	// opts can include `page_name`, `message`, `icon` or `img`
	if(!opts.page_name) {
		opts.page_name = frappe.get_route_str();
	}

	if(opts.icon) {
		opts.img = repl('<span class="%(icon)s message-page-icon"></span> ', opts);
	} else if (opts.img) {
		opts.img = repl('<img src="%(img)s" class="message-page-image">', opts);
	}

	var page = frappe.pages[opts.page_name] || frappe.container.add_page(opts.page_name);
	$(page).html(
		repl('<div class="page message-page">\
			<div class="text-center message-page-content">\
				%(img)s\
				<p class="lead">%(message)s</p>\
				<a class="btn btn-default btn-sm btn-home" href="#">%(home)s</a>\
			</div>\
		</div>', {
				img: opts.img || "",
				message: opts.message || "",
				home: __("Home")
			})
	);

	frappe.container.change_to(opts.page_name);
};

frappe.views.ModulesFactory = class ModulesFactory extends frappe.views.Factory {
	show() {
		if (frappe.pages.modules) {
			frappe.container.change_to('modules');
		} else {
			this.make('modules');
		}
	}

	make(page_name) {
		const assets = [
			'/assets/js/modules.min.js'
		];

		frappe.require(assets, () => {
			frappe.modules.home = new frappe.modules.Home({
				parent: this.make_page(true, page_name)
			});
		});
	}
};