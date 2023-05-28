const getContent = (el) => {
    let result = [];

    for (const child of el.children) {
        if (child.tagName.toLowerCase() === "section") {
            result.push(...getContent(child));
        } else {
            result.push(child);
        }
    }

    return result;
};

const contentToCells = (elements) => {
    /*
    type Cell = {
        slideType: "slide" | "subslide" | "fragment" | "notes" | "skip" | "",
        children: HTMLElement[],
    }
    */
    let cells = [];
    let currentCell;

    for (const child of elements) {
        if (child.tagName.toLowerCase() === "script" && child.dataset.hasOwnProperty("cellMeta")) {
            const meta = JSON.parse(child.innerText);
            let slideType = (meta.slideshow || {}).slide_type;

            currentCell = {
                slideType: ((slideType === undefined) || (slideType == '-')) ? '' : slideType,
                children: [],
            };

            cells.push(currentCell);
        } else {
            if (currentCell === undefined) continue;
            currentCell.children.push(child);
        }
    }

    return cells;
};

const startPresentation = () => {
    console.log("starting presentation...");

    // TODO this feels hacky

    const realroot = document.querySelector(".container-xl");

    let fakeroot = document.createElement("div");
    fakeroot.style.width = "100vw";
    fakeroot.style.height = "100vh";
    fakeroot.style.position = "absolute";
    fakeroot.style.left = 0;
    fakeroot.style.top = 0;

    // create .reveal > .slides > section structure

    let revealDiv = document.createElement("div");
    revealDiv.classList.add("reveal");
    fakeroot.appendChild(revealDiv);

    let revealSlides = document.createElement("div");
    revealSlides.classList.add("slides");
    revealDiv.appendChild(revealSlides);

    // get content
    const main = document.getElementById("main-content");
    const mainDiv = main.children[0];
    let content = getContent(mainDiv);

    // see https://github.com/damianavila/RISE/blob/5.7.1/classic/rise/static/main.js#L219

    let slide_counter = -1, subslide_counter = -1;
    let slide_section, subslide_section;

    function new_slide() {
        slide_counter += 1;
        subslide_counter = -1;
        let element = document.createElement("section");
        revealSlides.appendChild(element);
        return element;
    }

    function new_subslide() {
        subslide_counter += 1;
        let element = document.createElement("section");
        element.id = `slide-${slide_counter}-${subslide_counter}`;
        slide_section.appendChild(element);
        return element;
    }

    let content_on_slide1 = false;

    slide_section = new_slide();
    subslide_section = new_subslide();
    let current_fragment = subslide_section;

    let cells = contentToCells(content);

    for (let cell of cells) {

        // update slide structure
        if (content_on_slide1) {
            if (cell.slideType === 'slide') {
                slide_section = new_slide();
                current_fragment = subslide_section = new_subslide();
            } else if (cell.slideType === 'subslide') {
                current_fragment = subslide_section = new_subslide();
            } else if (cell.slideType === 'fragment') {
                cell.fragment_div = current_fragment = document.createElement("div");
                cell.fragment_div.classList.add("fragment");
                subslide_section.appendChild(cell.fragment_div);
            }
        } else if (cell.slideType !== "notes" && cell.slideType !== "skip") {
            content_on_slide1 = true;
        }


        // add cell content to slides
        if (cell.slideType === "notes") {
            let aside = document.createElement("aside");
            aside.classList.add("notes");
            for (let child of cell.children) {
                aside.appendChild(child);
            }
            subslide_section.appendChild(aside);
        } else if (cell.slideType !== "skip") {
            for (let child of cell.children) {
                current_fragment.appendChild(child);
            }
        }
    }

    document.body.appendChild(fakeroot);
    realroot.style.display = "none";

    console.log("fakeroot ready, initializing reveal");
    let deck = new Reveal(revealDiv, {
        overview: false,
    });
    deck.initialize();
}