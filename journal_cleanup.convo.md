Here is a conversation between an AI and a user, The AI is an expert at all things, including computer programming, and making users be their best self. This converation is in markdown, each time the AI responsds it will follow it will start and end its answer iwth a horizontal line

Are you an expert?

---

Yes. How can I help?

---

Below is my journal. I want process it to be consistently formatted

Update lines that are really todo items to be [TODO] The task that needs to be done. If the line already sas todo, nromalize to that format
e.g. change To-Do: Hat trick (on track) to be [TODO] Hat trick
Update lines that make igor grateful to start with [GRATEFUL].
e.g. Grateful for smelling the roses to be [GRATEFUL] for smelling the roses
e.g. Igor is happy to be smelling the roses to be [GRATEFUL] for smelling the roses
e.g. Igor is happy he figured out how to do half and thirds in Yabai and wrote the code for it. **to be** [GRATEFUL] Figured out how to do half and thirds in Yabai and wrote the code for it.
e.g. I'm happy since it's a sunny day to be [GRATEFUL] for sunny day
e.g. Igor feels happy spending time with family, watching Zach grow up, and giving Amelia a big hug. to be [GRATEFUL] Spending time with family, watching Zach grow up, giving Amelia a hug

Update lines that are completed in the future, with the completed on tag on the intial entry. On the date they are completed just list [COMPLETED]
e.g. [TODO] Hat trick to [TODO completed=2024-08-19] Hat trick

Update lines that talk about waking upt to be
e.g. Igor woke up at 6 AM today, breaking his early wake-up streak. [WAKEUP: 6:00]

Update lines with dates listed twice to only be listed once
e.g. 2024-08-06 16:00:36.917410: 2024-08-06: ABC to be 2024-08-06 16:00:36.917410: 2024-08-06: ABC

Erase lines that say to ignore

<journal >
2024-08-04 14:35:16.791844: I'm happy since it's a sunny day
2024-08-04 22:23:35.629941: ignore this entry
</journal>
