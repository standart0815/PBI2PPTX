# PBI2PPTX

A local desktop tool that turns a user's choice of Power BI report pages into one PowerPoint deck, built from the user's own template, with each page shown as an image.

## Power BI side

**User**:
A person signed in with their own Microsoft work account. They see and export only what their Power BI permissions allow.
_Avoid_: account, login

**Workspace**:
A Power BI workspace, including the User's personal "My workspace", that the User can open directly.
_Avoid_: group

**Power BI App**:
A packaged set of reports published from a Workspace to consumers, who may have no access to the Workspace itself.
_Avoid_: "the app" on its own (it is ambiguous with this tool), org app

**Report**:
A Power BI report that the User reaches through a Workspace or a Power BI App.
_Avoid_: dashboard

**Report Page**:
One page of a Report. It is the unit that becomes one slide.
_Avoid_: tab, section, ReportSection

**Hidden Page**:
A Report Page that the report author hid from viewers, such as a tooltip or drill-through page. It is never offered for selection.

**Default State**:
A Report Page as published, without any viewer's slicer selections, personal bookmarks or persisted filters.
_Avoid_: current state, my view

**Filter**:
A condition on a report field (table, column, values) entered by the User. It is passed to Power BI in the page address and applied on top of the Default State before the page is captured.
_Avoid_: slicer, bookmark

**Power BI Window**:
The browser window that the tool opens and controls, in which the User signs in to Power BI and browses to the pages they want to add.
_Avoid_: embedded browser, viewer

**Page URL**:
The address of a Report Page in Power BI, as shown in the Power BI Window. It is how an Entry refers to its page.
_Avoid_: link, deep link

## Deck side

**Selection**:
The named, ordered list of Entries a User assembles for one Deck. It may mix Reports from different Workspaces and Power BI Apps.
_Avoid_: page list, input list

**Entry**:
One item in a Selection: a Page URL, its slide title and its Filters. The same Report Page can appear in several Entries.
_Avoid_: selected page, item, row

**Saved Selection**:
A Selection saved as a JSON file that the User keeps and can load again later. It does not contain the Template.
_Avoid_: preset, profile, config

**Template**:
The User-supplied PowerPoint template (.potx), picked for each Export, that defines the Deck's look and slide layouts.
_Avoid_: master, theme, design

**Slide Layout**:
The one layout from the Template, chosen by the User, that every Entry's slide uses.
_Avoid_: master, design

**Image Area**:
The part of a slide that a Page Image may occupy. By default it is the full slide width, between the bottom of the title (the header) and the top of any footers. If the Slide Layout has a picture placeholder, that placeholder's box is the Image Area instead.
_Avoid_: content area, body, canvas

**Decorative Graphic**:
A picture or shape that a Template's layout or master shows on every slide, and that is not a placeholder. If it reaches into the Image Area, the User is warned.
_Avoid_: artwork, illustration, background

**Page Image**:
The rendered picture of one Entry's Report Page in its Default State with its Filters applied.
_Avoid_: screenshot, snapshot, export

**Render Language**:
The language, and with it the number and date formats, in which Page Images are rendered. It is German by default and can be switched per Export.
_Avoid_: locale, UI language

**Export**:
One run that turns a Selection and a Template into a Deck.
_Avoid_: job, conversion, download

**Deck**:
The PowerPoint file an Export produces, with one slide per Entry.
_Avoid_: presentation, PowerPoint, report

**Error Slide**:
The slide that takes the place of an Entry whose Report Page could not be captured, for example because it was deleted or the User has no access. It names the page and the reason.
_Avoid_: placeholder slide, blank slide
