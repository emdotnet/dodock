// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import { Calendar } from "@fullcalendar/core";
import timeGridPlugin from "@fullcalendar/timegrid";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";

frappe.provide("frappe.views.calendar");

const day_map = {
	Sunday: 0,
	Monday: 1,
	Tuesday: 2,
	Wednesday: 3,
	Thursday: 4,
	Friday: 5,
	Saturday: 6,
};

frappe.views.CalendarView = class CalendarView extends frappe.views.ListView {
	static load_last_view() {
		const route = frappe.get_route();
		if (route.length === 3) {
			const doctype = route[1];
			const user_settings = frappe.get_user_settings(doctype)["Calendar"] || {};
			route.push(user_settings.last_calendar || "default");
			frappe.set_route(route);
			return true;
		} else {
			return false;
		}
	}

	toggle_result_area() {}

	get view_name() {
		// __("Calendar")
		return "Calendar";
	}

	setup_page() {
		this.hide_page_form = false;
		super.setup_page();
	}

	async setup_defaults() {
		await super.setup_defaults();
		this.page_title = __("{0} Calendar", [this.page_title]);
		this.calendar_settings = frappe.views.calendar[this.doctype] || {};
		this.calendar_name = frappe.get_route()[3];
	}

	before_refresh() {
		super.before_refresh();
		if (
			this.calendar_settings.filters &&
			this.calendar_settings.filters.length > 0 &&
			Array.isArray(this.calendar_settings.filters[0])
		) {
			this.filter_area.add(this.calendar_settings.filters);
		}
	}

	setup_view() {
		this.sort_selector.wrapper.hide();
	}

	before_render() {
		super.before_render();
		this.save_view_user_settings({
			last_calendar: this.calendar_name,
		});
	}

	render() {
		if (this.calendar) {
			this.calendar.refresh();
			return;
		}

		this.load_lib
			.then(() => this.get_calendar_preferences())
			.then((options) => {
				this.calendar = new frappe.views.Calendar(options);
			});
	}

	get_calendar_preferences() {
		const options = {
			doctype: this.doctype,
			parent: this.$result,
			page: this.page,
			list_view: this,
		};
		const calendar_name = this.calendar_name;

		return new Promise((resolve) => {
			if (calendar_name.toLowerCase() === "default") {
				Object.assign(options, frappe.views.calendar[this.doctype]);
				resolve(options);
			} else {
				frappe.model.with_doc("Calendar View", calendar_name, () => {
					const doc = frappe.get_doc("Calendar View", calendar_name);
					if (!doc) {
						frappe.show_alert(
							__("{0} is not a valid Calendar. Redirecting to default Calendar.", [
								calendar_name.bold(),
							])
						);
						frappe.set_route("List", this.doctype, "Calendar", "default");
						return;
					}
					Object.assign(options, {
						field_map: {
							id: "name",
							start: doc.start_date_field,
							end: doc.end_date_field,
							title: doc.subject_field,
							allDay: doc.all_day_field,
							status: doc.status_field,
							color: doc.color_field,
							rrule: doc.recurrence_rule_field,
							secondary_status: doc.secondary_status_field,
						},
						secondary_status_color: doc.secondary_status.reduce(
							(obj, f) => Object.assign(obj, { [f.value]: f.color }),
							{}
						),
						calendar_defaults: {
							slots_start_time: doc.daily_minimum_time,
							slots_end_time: doc.daily_maximum_time,
							first_day: doc.first_day ? day_map[doc.first_day] : null,
							display_event_time: doc.display_event_time == 1 ? true : false,
							display_event_end: doc.display_event_end == 1 ? true : false,
						},
					});

					resolve(options);
				});
			}
		});
	}

	get required_libs() {}
};

frappe.views.Calendar = class frappeCalendar {
	constructor(options) {
		$.extend(this, options);
		this.fullcalendar = null;
		this.calendar_defaults =
			this.calendar_defaults && Object.keys(this.calendar_defaults)
				? this.calendar_defaults
				: {
						display_event_time: true,
						display_event_end: true,
				  };
		this.sidebar_menu = this.list_view.list_sidebar?.sidebar.find(".sidebar-menu");

		this.field_map = this.field_map || {
			id: "name",
			start: "start",
			end: "end",
			allDay: "all_day",
			convertToUserTz: "convert_to_user_tz",
		};
		this.get_default_options();
	}

	get_default_options() {
		return new Promise((resolve) => {
			let initialView = localStorage.getItem("cal_initialView");
			let weekends = localStorage.getItem("cal_weekends");
			let defaults = {
				initialView:
					initialView &&
					["timeGridDay", "timeGridWeek", "dayGridMonth"].includes(initialView)
						? initialView
						: "dayGridMonth",
				weekends: weekends ? weekends : true,
			};
			resolve(defaults);
		}).then((defaults) => {
			Object.assign(this.calendar_defaults, defaults);
			this.make_page();
			this.setup_options(this.calendar_defaults);
			this.make();
			this.setup_view_mode_button(this.calendar_defaults);
			this.bind();
		});
	}

	make_page() {
		const me = this;

		// add links to other calendars
		me.page.clear_user_actions();
		$.each(frappe.boot.calendars, function (i, doctype) {
			if (frappe.model.can_read(doctype)) {
				me.page.add_menu_item(__(doctype), function () {
					frappe.set_route("List", doctype, "Calendar");
				});
			}
		});

		$(this.parent).on("show", function () {
			me.fullcalendar.refetchEvents();
		});
	}

	make() {
		const me = this;
		this.$wrapper = this.parent;
		this.$cal = $("<div>").appendTo(this.$wrapper);
		this.footnote_area = frappe.utils.set_footnote(
			this.footnote_area,
			this.$wrapper,
			__("Select or drag across time slots to create a new event.")
		);
		this.footnote_area.css({ "border-top": "0px" });

		this.fullcalendar = new Calendar(this.$cal[0], this.cal_options);
		this.fullcalendar.render();

		this.$wrapper.find(".fc-today-button").prepend(frappe.utils.icon("today"));

		if (this.secondary_status_color) {
			this.show_secondary_status_legend();
		}
	}

	setup_view_mode_button(defaults) {
		const me = this;
		$(me.footnote_area).find(".btn-weekend").detach();
		const btnTitle = defaults.weekends ? __("Hide Weekends") : __("Show Weekends");
		const btn = `<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`;
		me.footnote_area.append(btn);
	}

	set_localStorage_option(option, value) {
		localStorage.removeItem(option);
		localStorage.setItem(option, value);
	}

	bind() {
		const me = this;
		const btn_group = me.$wrapper.find(".fc-button-group");
		btn_group.on("click", ".fc-button", function () {
			const value = $(this).hasClass("fc-timeGridWeek-button")
				? "timeGridWeek"
				: $(this).hasClass("fc-timeGridDay-button")
				? "timeGridDay"
				: "dayGridMonth";
			me.set_localStorage_option("cal_initialView", value);
		});

		me.$wrapper.on("click", ".btn-weekend", function () {
			me.cal_options.weekends = !me.cal_options.weekends;
			me.fullcalendar.setOption("weekends", me.cal_options.weekends);
			me.set_localStorage_option("cal_weekends", me.cal_options.weekends);
			me.setup_view_mode_button(me.cal_options);
		});
	}

	show_secondary_status_legend() {
		if (!this.sidebar_menu) return;
		frappe.model.with_doctype(this.doctype, () => {
			const meta = frappe.get_meta(this.doctype);
			const status_colors = Object.keys(this.secondary_status_color)
				.map((f) => {
					return `
					<div><span class="flex align-items-center status-color ${this.secondary_status_color[f]}">${__(
						f
					)}</span></div>
				`;
				})
				.join("");
			this.sidebar_menu.find(".calendar-status-section").remove();
			this.sidebar_menu.append(`
				<div class="calendar-status-section">
					<li class="sidebar-label">${__(
						meta.fields.filter(
							(f) => f.fieldname == this.field_map.secondary_status
						)[0].label
					)}</li>
					<div>${status_colors}</div>
				</div>
			`);
		});
	}

	get_system_datetime(date) {
		date._offset = moment(date).tz(frappe.sys_defaults.time_zone)._offset;
		return frappe.datetime.convert_to_system_tz(date);
	}

	setup_options(defaults) {
		const me = this;

		this.cal_options = {
			locale: frappe.get_cookie("preferred_language") || frappe.boot.lang || "en",
			plugins: [interactionPlugin, timeGridPlugin, dayGridPlugin],
			headerToolbar: {
				left: "dayGridMonth,timeGridWeek,timeGridDay",
				center: "prev,title,next",
				right: "today",
			},
			height: "auto",
			editable: true,
			selectable: true,
			selectMirror: true,
			forceEventDuration: true,
			displayEventTime: defaults.display_event_time,
			displayEventEnd: defaults.display_event_end,
			initialView: defaults.initialView,
			weekends: defaults.weekends,
			nowIndicator: true,
			buttonText: {
				today: __("Today"),
				month: __("Month"),
				week: __("Week"),
				day: __("Day"),
			},
			events: function (start, end, timezone, callback) {
				return frappe.call({
					method: me.get_events_method || "frappe.desk.calendar.get_events",
					type: "GET",
					args: me.get_args(start, end),
					callback: function (r) {
						var events = r.message || [];
						events = me.prepare_events(events);
						callback(events);
					});
			},
			eventClick: function (info) {
				// edit event description or delete
				const doctype =
					info.event.doctype || info.event.extendedProps.doctype || me.doctype;
				if (frappe.model.can_read(doctype)) {
					frappe.set_route("Form", doctype, info.event.id);
				}
			},
			eventDrop: function (info) {
				me.update_event(info);
				$(info.el).tooltip("dispose");
			},
			eventResize: function (info) {
				me.update_event(info);
				$(info.el).tooltip("dispose");
			},
			select: function (selectionInfo) {
				if (
					selectionInfo.view.type === "dayGridMonth" &&
					selectionInfo.end - selectionInfo.start === 86400000
				) {
					// detect single day click in month view
					return;
				}
				const event = frappe.model.get_new_doc(me.doctype);

				event[me.field_map.start] = me.get_system_datetime(selectionInfo.start);

				if (me.field_map.end) {
					event[me.field_map.end] = me.get_system_datetime(selectionInfo.end);
				}

				if (me.field_map.allDay) {
					event[me.field_map.allDay] = selectionInfo.allDay;

					if (selectionInfo.allDay) {
						const last_second = moment(selectionInfo.end).subtract(1, "seconds");
						event[me.field_map.end] = me.get_system_datetime(last_second.toDate());
					}
				}

				frappe.set_route("Form", me.doctype, event.name);
			},
			dateClick: function (info) {
				if (info.view.type === "dayGridMonth") {
					me.fullcalendar.changeView("timeGridDay");
					me.fullcalendar.gotoDate(info.date);

					// update "active view" btn
					me.$wrapper.find(".fc-dayGridMonth-button").removeClass("active");
					me.$wrapper.find(".fc-timeGridDay-button").addClass("active");
				}
				return false;
			},
			buttonText: {
				today: __("Today"),
				month: __("Month"),
				week: __("Week"),
				day: __("Day"),
			},
			allDayContent: function () {
				return __("All Day");
			},
			eventDidMount: function (info) {
				$(info.el).tooltip({
					title: frappe.utils.html2text(info.event.title),
					placement: "auto",
				});
			},
			eventWillUnmount: function (info) {
				$(info.el).tooltip("dispose");
			},
			slotMinTime: defaults.slots_start_time || "06:00:00",
			slotMaxTime: defaults.slots_end_time || "22:00:00",
			firstDay: defaults.first_day ?? frappe.datetime.get_first_day_of_the_week_index(),
		};

		if (this.options) {
			$.extend(this.cal_options, this.options);
		}
	}

	get_args(start, end) {
		return {
			doctype: this.doctype,
			start: this.get_system_datetime(start),
			end: this.get_system_datetime(end),
			filters: this.list_view.filter_area.get(),
			field_map: this.field_map,
		};
	}

	refresh() {
		this.fullcalendar.refetchEvents();
	}

	prepare_events(events) {
		const me = this;
		return (events || []).map((d) => {
			d.id = d.name;
			d.editable = frappe.model.can_write(d.doctype || me.doctype);
			d.classNames = d.classNames || [];

			// do not allow submitted/cancelled events to be moved / extended
			if (d.docstatus && d.docstatus > 0) {
				d.editable = false;
			}

			$.each(me.field_map, function (target, source) {
				d[target] = d[source];
			});

			if (!me.field_map.allDay && !me.no_all_day) {
				d.allDay = true;
			}
			if (!me.field_map.convertToUserTz) d.convertToUserTz = true;

			// convert to user tz
			if (d.convertToUserTz) {
				d.start = frappe.datetime.convert_to_user_tz(d.start);
				d.end = frappe.datetime.convert_to_user_tz(d.end);
			}

			// show event on single day if start or end date is invalid
			if (!frappe.datetime.validate(d.start) && d.end) {
				d.start = frappe.datetime.add_days(d.end, -1);
			}

			if (d.start && !frappe.datetime.validate(d.end)) {
				d.end = frappe.datetime.add_days(d.start, 1);
			}

			if ((d.secondary_status || d.status) && me.secondary_status_color) {
				d.classNames.push(me.secondary_status_color[d.secondary_status || d.status] || "");
			}

			me.fix_end_date_for_event_render(d);
			me.prepare_colors(d);

			d.title = frappe.utils.html2text(d.title);

			return d;
		});
	}

	prepare_colors(d) {
		let color;

		color = d.color;
		if (!frappe.ui.color.validate_hex(color) || !color) {
			color = color
				? frappe.ui.color.get_color_shade(color, "default")
				: undefined || frappe.ui.color.get("blue", "default");
		}
		d.backgroundColor = color;
		d.borderColor = color;
		d.textColor = frappe.ui.color.get_contrast_color(color);

		return d;
	}

	update_event(info) {
		var me = this;
		let firstEvent = info.event;
		if (info.relatedEvents && info.relatedEvents[0]) {
			// let ok = false;
			// const dialog = new frappe.ui.Dialog();
			// me.refresh();
			const maybeFirst = info.relatedEvents[0];
			if (maybeFirst.start < firstEvent.start) {
				firstEvent = maybeFirst;
			}
		}
		frappe.model.remove_from_locals(
			firstEvent.extendedProps?.doctype || me.doctype,
			firstEvent.id
		);
		return frappe.call({
			method: me.update_event_method || "frappe.desk.calendar.update_event",
			args: me.get_update_args(firstEvent),
			callback: function (r) {
				if (r.exc) {
					frappe.show_alert(__("Unable to update event"));
					info.revert();
				} else {
					if (firstEvent.extendedProps?.rrule) {
						// Fetch some instances of the recurring event that might
						// be missing because they were out of the displayed range
						// but now should be displayed because the recurring event
						// was moved to an earlier date.
						me.refresh();
					}
				}
			},
			error: function () {
				info.revert();
			},
		});
	}

	get_update_args(event) {
		const me = this;
		let args = {
			name: event.id,
		};

		args[this.field_map.start] = me.get_system_datetime(event.start);

		if (this.field_map.allDay) args[this.field_map.allDay] = event.allDay;

		if (this.field_map.end) {
			if (!event.end) {
				event.end = event.start.add(1, "hour");
			}

			args[this.field_map.end] = me.get_system_datetime(event.end);

			if (args[this.field_map.allDay]) {
				args[this.field_map.end] = moment(event.end).subtract(1, "seconds");
			}
		}

		args.doctype = event.doctype || this.doctype;

		return { args: args, field_map: this.field_map };
	}

	fix_end_date_for_event_render(event) {
		if (event.allDay) {
			// We use inclusive end dates. This workaround fixes the rendering of events
			event.end = event.end
				? this.get_system_datetime(moment(event.end).add(1, "day"))
				: null;
		}
	}
};
