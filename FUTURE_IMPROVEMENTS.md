# Future improvements

Ideas we've agreed are worth doing, but not yet. Each one goes in only after it
passes the same sample-video test as the v1 pipeline.

## Group photos by room (room transitions and 360° room views)

**What:** on the photos page, let the broker mark which photos show the same
room. The pipeline can then treat a room as one scene: a smooth transition
between its photos and a 360° (orbit) move around the room instead of separate
clips.

**Two ways to do it (pick one when we build it):**

1. **Tag photos with a room.** Each photo gets a room label (Living room,
   Kitchen, Bedroom 1, Bathroom 1, ...). Simple to add to the current grid, and
   works when the broker uploads everything at once from the gallery.
2. **One upload section per room.** The details page already asks for bedrooms
   and bathrooms; the photos page would show a section for each (Bedroom 1,
   Bedroom 2, Bathroom 1, plus Living room, Kitchen, Exterior, Other). Clearer
   for the broker, but more tapping on a phone.

**What it touches:**

- `Photo` gets a `room` field, and the video order becomes rooms first, then
  photos within each room.
- `ShotPlanner` receives photos grouped by room, so it can plan one multi-photo
  camera move per room.
- `ClipGenerator` needs a model that can take two or more photos of a room
  (first and last frame, or reference images) to make the 360° move. To be
  checked in the model tests.
- The 10-photo limit and ~6 s per photo may need rethinking per room.

## Already planned for later (from the v1 plan)

- Voiceover
- AI lifestyle actors
- Custom camera moves
- Music library and music choice
- More templates and agency branding
- Accounts with server-side saved agent profiles (v1 keeps them in the browser)
