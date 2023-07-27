frappe.ui.CardGroup = class CardGroup {
	constructor({
		wrapper,
		cards
	}) {
		this.wrapper = wrapper;
		this.cards = cards;

		this.build()
	}

	build() {
		const cards_content = this.cards.map(c => {
			return new Card(c)
		})

		const card_deck = document.createElement("div");
		card_deck.classList.add("card-deck", "responsive-card-deck");
		cards_content.forEach(c => card_deck.appendChild(c))

		this.wrapper.appendChild(card_deck)
	}

}


class Card {
	constructor({
		title,
		description,
		image,
		image_alt,
		primary_button_label,
		primary_button_action
	}) {
		Object.assign(this, arguments[0])

		return this.build()
	}

	build() {
		const card_canva = document.createElement("div");
		card_canva.classList.add("card-in-card-deck", "card", "h-100");

		if (this.image) {
			const card_image = document.createElement("img");
			card_image.classList.add("card-img-top");
			card_image.src = this.image
			card_image.alt = this.title
			card_canva.appendChild(card_image)
		}

		const card_body = document.createElement("div");
		card_body.classList.add("card-body");

		const card_title = document.createElement("h5");
		card_title.classList.add("card-title");
		card_title.innerText = this.title || "";
		card_body.appendChild(card_title)

		const card_description = document.createElement("p");
		card_description.classList.add("card-text");
		card_description.innerHTML = this.description || "";
		card_body.appendChild(card_description)

		if (this.primary_button_action) {
			const card_button = document.createElement("p");
			card_button.classList.add("btn", "btn-primary");
			card_button.innerText = this.primary_button_label || __("Select")

			card_button.addEventListener("click", (e) => {
				e.preventDefault();
				this.primary_button_action && this.primary_button_action()
			});

			card_body.appendChild(card_button)
		}

		card_canva.appendChild(card_body)


		return card_canva
	}
}