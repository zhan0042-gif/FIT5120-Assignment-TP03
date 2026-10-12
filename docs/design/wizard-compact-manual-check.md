# Compact Plan Wizard: Manual Check

Run in Chrome at `http://localhost:5173/plan` (backend running, a household with a saved
address). Tick each box when the expected result happens. Record anything unexpected with
the steps that led to it.

- [ ] **New household.** Five screens in order (Household, Daytime, Vehicles, Places, Jobs). The progress bar shows five parts. Save and continue works on each.
- [ ] **Vehicles, blank description.** Answer yes, add a second vehicle, set its type to "Other" and leave the description empty. Save is blocked, the summary lists the message, and focus lands on the field.
- [ ] **Vehicles, first choice and backup.** Choose a first vehicle: it disappears from the backup choices. Tick a backup, save, reload: both persist.
- [ ] **Vehicles, answer no.** With vehicles saved, answer no: the vehicles disappear and the plan saves as "No private vehicle".
- [ ] **One vehicle.** With only one vehicle the screen says to add a second to choose a backup.
- [ ] **Jobs.** Choose "Something else" and leave it blank: save is blocked. Type a name: save works. Choose the same person as main and backup: the backup clears.
- [ ] **Review.** Five rows with the right status. Edit on Vehicles opens that screen with every answer visible. Change one name, then **Save and return to review** returns to Review.
- [ ] **Back while editing.** Edit, then Back: returns to Review without saving.
- [ ] **Unsaved warning.** Open a screen and leave without typing: no warning. Type something and leave: the warning appears.
- [ ] **Blank cards.** Add a person and a job, leave them empty, save: neither is saved as an empty record.
- [ ] **Deep links.** `/plan?section=transport`, `?section=people` and `?section=review` open Vehicles, Household and Review.
- [ ] **Phone width and keyboard.** At 375 px wide, cards are one column and nothing scrolls sideways. With the keyboard only, Tab reaches every field and button with a visible focus ring, and the error summary links jump to the field.
- [ ] **Voice.** With voice on, "go to my plan" still opens `/plan`.
