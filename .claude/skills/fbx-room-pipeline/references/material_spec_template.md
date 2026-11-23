# <Room> — material spec (template)

Client-specified material mapping, keyed to the cluster IDs shown in
`docs/validation/<room>_clusters_*.png`. Drives `scripts/build_scene.py`.

## Laminates / finishes
| Code | Name / finish | Grain (native) | Source image |
|------|---------------|----------------|--------------|
| <G23> | <Coastal Pear / matte> | vertical | materials/<...>.png |
| <H53> | <Brushed Elm / dark>   | vertical | materials/<...>.png |

## Furniture inventory (from validation renders)
- Cabinet_1 … = <what each is: base cabinet, mobile pedestal, wall cabinet, worktop…>
- Note any non-furniture: windows, doors, structure, junk to drop.

## Materials by role (drawer cabinets / pedestals)
| Panel role   | Laminate | Grain      |
|--------------|----------|------------|
| Drawer fronts| <G23>    | horizontal |
| Sides        | <H53>    | vertical   |
| Backs        | <H53>    | vertical   |
| Top & bottom | <H53>    | horizontal |
| Drawer boxes | black    | —          |

## Work surfaces / worktops
- Laminate + grain (e.g. G23, horizontal along length). Legs: black metal.
- Desk back/modesty panels: laminate + grain (confirm — often H53 horizontal).

## Room shell
- Walls: <finish> (each a separate node for web toggles).
- Doors + window frames: <"general material", e.g. aluminium/white/black>.
- Glass: <clear transmission / tinted / mirror>.
- Floor/ceiling: usually absent in these exports.

## Hardware / handles
- Base hardware: black. Merge; drop only invisible micro-clutter (zero naked-eye loss).
- Handle swap: <model + reference>. Drawer=horizontal-centred, door=vertical-near-edge.

## Grain / front-detection notes
- Front face = exterior vertical face with the most panels (drawer fronts stack).
- Verify grain with flat-on elevation renders per role.
