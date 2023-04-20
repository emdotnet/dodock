// Copyright (c) 2020, Dokos SAS and Contributors
// See license.txt

frappe.provide("frappe.events");

import "frappe/public/js/frappe/ui/web_calendar";

frappe.events.EventsPortalView = class EventsPortalView extends frappe.ui.BaseWebCalendar {
	constructor(opts) {
		opts.wrapper ??= opts.parent;
		super(opts);
	}

	calendar_options() {
		return Object.assign(super.calendar_options(), {
			eventClassNames: "events-calendar",
			initialView: frappe.is_mobile() ? "listDay" : "dayGridMonth",
			headerToolbar: {
				left: frappe.is_mobile() ? "today" : "dayGridMonth,timeGridWeek",
				center: "prev,title,next",
				right: frappe.is_mobile() ? "" : "today",
			},
			selectable: true,
			slotMinTime: "09:00:00",
			slotMaxTime: "17:00:00",
		});
	}

	onEventsUpdated() {
		this.set_min_max_times({ min: "09:00:00", max: "17:00:00" });
	}

	async getEvents(parameters) {
		return frappe
			.call({
				method: "frappe.desk.doctype.event.event.get_prepared_events",
				args: {
					start: this.format_ymd(parameters.start),
					end: this.format_ymd(parameters.end),
				},
			})
			.then((result) => {
				return result.message || [];
			});
	}

	onEventClick(event) {
		const dialog = new frappe.ui.Dialog({
			size: "large",
			title: __(event.event.title),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "event_description",
				},
			],
		});

		event.event.extendedProps.route &&
			dialog.set_primary_action(__("See details"), () => {
				window.location.href = "/" + event.event.extendedProps.route;
			});
		dialog.fields_dict.event_description.$wrapper.html(event_details(event));
		dialog.show();
	}
};

const event_details = (event) => {
	const image = event.event.extendedProps.image
		? `<div style="background: url(${event.event.extendedProps.image}) center/contain no-repeat;min-width: 10%;"></div>`
		: "";
	const description = event.event.extendedProps.description
		? event.event.extendedProps.description
		: `<div>${__("No description")}</div>`;
	return `
		<div class="calendar-event">
			<div class="card-body flex justify-content-start">
				${image}
				<div class=${event.event.extendedProps.image ? "pl-2" : ""}>
					<h5 class="card-title">${event.event.extendedProps.subject}</h5>
					${description}
				</div>
			</div>
		</div>
	`;
};
