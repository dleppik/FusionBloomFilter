# FusionBloomFilter © 2024 by David Leppik is licensed under Creative Commons Attribution-NonCommercial 4.0 International
# See https://creativecommons.org/licenses/by-nc/4.0/

import adsk.core, adsk.fusion, traceback
import hashlib

default_category_name = 'Fruit'
default_category_items = 'Tomato\nApple\nBanana\nPear\nCucumber'
# Veggies (for contrast): Carrot, Lettuce, Beet, Broccoli, Cauliflower, Tomato, Cucumber


# Fusion coordinates/sizes are in cm
mm = 0.1
grid_spacing = 1.5 * mm
pixel_size = 3 * mm
grid_size = (pixel_size + grid_spacing) * 16
grid_margin = 2 * mm
pixel_height = 1.5 * mm
card_base_thickness = 1 * mm
padding_between_cards = 2.0 + pixel_size + card_base_thickness

tolerance = 0.2 * mm

card_top_left = (grid_margin + grid_spacing + grid_size, 10)
filter_card_bottom_right = (-grid_margin - grid_spacing, 0)
item_card_bottom_right = (-grid_margin - grid_spacing, -4)

# The number of hash functions combined to form a sparse hash.
# Also the maximum number of pixels set in an item hash.
# The maximum number of pixels set in the Bloom filter is
# this times the number of items.
num_hashes = 10

# Fusion global variables to keep references
_app = None
_ui = None
_handlers = []

#
# Bloom filter utils
#

def create_bloom_filter(entries):
    """
    Create a toy bloom filter containing the given entries.
    """
    bloom = set()
    for item in entries:
        add_to_bloom_filter(item, bloom)
    return bloom

def item_in_bloom(item: str, bloom) -> bool:
    item_hash = create_bloom_filter([item])
    return item_hash & bloom == item_hash

def add_to_bloom_filter(string_to_add: str, bloom):
    """
    Add to a toy bloom filter. In a real bloom filter, we'd use
    a bitmap rather than a set of numbers, since the whole point is to be
    memory efficient.
    """
    global num_hashes
    encoded_string = string_to_add.encode('utf-8')

    # A Bloom filter generates multiple hashes per item.
    # Since all bits are equally probable in a high-quality hash,
    # we can slice up a 265-bit hash into up to 32 1-byte hashes.
    sha256_hash = hashlib.sha256(encoded_string).digest()

    for i in range(num_hashes):
        bloom.add(sha256_hash[i])


def coordinates_from_byte(b):
    """
    Spit a byte into x, y coordinates in the range (0..15)
    where x gets the high bits and y gets the low bits.
    """
    x = (b & 0xF0) >> 4  # Conveniently, the masks can be used as test input
    y = b & 0x0F
    return x, y

def byte_for_coordinate(x: int, y: int):
    return (y & 0xf) + ((x & 0xf) << 4)


#
# UI handlers
#

class BloomCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            # Get the command inputs
            inputs = args.command.commandInputs
            name = inputs.itemById('nameInput').value
            items_str = inputs.itemById('itemsInput').text

            # Get the active design and component
            design = _app.activeProduct
            component = design.activeComponent

            items = [s.strip() for s in items_str.split('\n')]
            bloom = create_bloom_filter(items)

            draw_bloom_component(bloom, name, component)

            item_spacing = padding_between_cards
            item_height = item_spacing
            for item in items:
                draw_hash_item(item, item_height, component)
                item_height = item_height + padding_between_cards
        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class BloomCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):

        try:
            cmd = args.command

            on_execute = BloomCommandExecuteHandler()
            cmd.execute.add(on_execute)
            on_destroy = BloomCommandDestroyHandler()
            cmd.destroy.add(on_destroy)
            _handlers.append(on_execute)
            _handlers.append(on_destroy)

            # Define the inputs

            inputs = cmd.commandInputs
            inputs.addStringValueInput('nameInput', 'Name', default_category_name)
            inputs.addTextBoxCommandInput('itemsInput', 'Items', default_category_items, 5, False)

        except:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class BloomCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # when the command is done, terminate the script
            # this will release all globals which will remove all event handlers
            adsk.terminate()
        except:
            if _ui:
                _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


#
# Sketch commands
#

def draw_bloom_component(bloom, name, parent_component):
    global grid_spacing, pixel_size, grid_size, grid_margin, pixel_height
    occurrence = parent_component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    component = occurrence.component
    component.name = name

    sketches = component.sketches
    xy_plane = component.xYConstructionPlane
    sketch = sketches.add(xy_plane)
    draw_bloom_grid(bloom, component, sketch)

    # Draw the name
    draw_bloom_text(name, component, xy_plane)

def draw_bloom_grid(bloom, component, sketch):
    """
    Draw Bloom sketch and boxes. This must be done in a sketch with no other profiles.
    """
    global grid_spacing, pixel_size, grid_size, grid_margin, pixel_height, card_top_left, filter_card_bottom_right

    point_tolerance = 0.0
    full_point_size = pixel_size + grid_spacing

    lines = sketch.sketchCurves.sketchLines

    for grid_x in range(16):
        for grid_y in range(16):
            byte = byte_for_coordinate(grid_x, grid_y)
            if byte in bloom:
                block_x = grid_x * full_point_size
                block_y = grid_y * full_point_size

                p1_offset = grid_spacing + point_tolerance
                p1 = adsk.core.Point3D.create(block_x + p1_offset, block_y + p1_offset, 0)

                p2_offset = grid_spacing + pixel_size - point_tolerance
                p2 = adsk.core.Point3D.create(block_x + p2_offset, block_y + p2_offset, 0)
                lines.addTwoPointRectangle(p1, p2)

    # Draw outline and extrude
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(card_top_left[0], card_top_left[1], 0),
        adsk.core.Point3D.create(filter_card_bottom_right[0], filter_card_bottom_right[1], 0))
    extrudes = component.features.extrudeFeatures
    extrudes.addSimple(sketch.profiles.item(sketch.profiles.count - 1),
                       adsk.core.ValueInput.createByReal(pixel_height),
                       adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

def draw_hash_item(item: str, height_cm: float, parent_component):
    occurrence = parent_component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    component = occurrence.component
    component.name = item

    # create plane
    planes = component.constructionPlanes
    plane_input = planes.createInput()
    offset = adsk.core.ValueInput.createByReal(height_cm)
    plane_input.setByOffset(component.xYConstructionPlane, offset)
    plane = planes.add(plane_input)

    draw_hash_sketches(item, component, plane)
    draw_item_text(item, component, plane)


def draw_hash_sketches(item: str, component, plane):
    global grid_spacing, pixel_size, grid_size, grid_margin, pixel_height, card_top_left
    global item_card_bottom_right, tolerance

    full_point_size = pixel_size + grid_spacing

    sketches = component.sketches
    sketch1 = sketches.add(plane)
    lines = sketch1.sketchCurves.sketchLines

    item_hash = create_bloom_filter([item])

    for grid_x in range(16):
        for grid_y in range(16):
            byte = byte_for_coordinate(grid_x, grid_y)
            if byte in item_hash:
                block_x = grid_x * full_point_size
                block_y = grid_y * full_point_size

                p1_offset = grid_spacing + tolerance
                p1 = adsk.core.Point3D.create(block_x + p1_offset, block_y + p1_offset, 0)

                p2_offset = grid_spacing + pixel_size - tolerance
                p2 = adsk.core.Point3D.create(block_x + p2_offset, block_y + p2_offset, 0)
                lines.addTwoPointRectangle(p1, p2)

    # Extrude all profiles. It's too hard to determine which ones we want, hence doing this in a fresh sketch

    profiles_to_extrude1 = adsk.core.ObjectCollection.create()
    for prof_index in range(sketch1.profiles.count):
        profiles_to_extrude1.add(sketch1.profiles.item(prof_index))
    extrudes = component.features.extrudeFeatures
    extrudes.addSimple(profiles_to_extrude1,
                       adsk.core.ValueInput.createByReal(-pixel_height),  # Negative to point toward filter
                       adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    # Draw a containing rectangle and extrude it in its own sketch in order to ignore the interior profiles

    sketch2 = sketches.add(plane)
    lines2 = sketch2.sketchCurves.sketchLines
    lines2.addTwoPointRectangle(
        adsk.core.Point3D.create(card_top_left[0], card_top_left[1], 0),
        adsk.core.Point3D.create(item_card_bottom_right[0], item_card_bottom_right[1], 0))

    extrudes.addSimple(sketch2.profiles.item(0),
                       adsk.core.ValueInput.createByReal(card_base_thickness), # Positive to preserve hash extrude length
                       adsk.fusion.FeatureOperations.JoinFeatureOperation)

    return [sketch1, sketch2]

def draw_item_text(name: str, component, plane):
    global grid_spacing, pixel_size, grid_size, grid_margin, pixel_height, tolerance
    global card_top_left, item_card_bottom_right, filter_card_bottom_right

    plate_extrude_distance = pixel_height + (0.1 * mm) # use tighter tolerance for good looks

    sketches = component.sketches
    sketch = sketches.add(plane)

    # Extrude a plate

    extrudes = component.features.extrudeFeatures

    lines = sketch.sketchCurves.sketchLines
    plate_top_y =  filter_card_bottom_right[1] - tolerance

    p1 = adsk.core.Point3D.create(card_top_left[0], plate_top_y, 0)
    p2 = adsk.core.Point3D.create(item_card_bottom_right[0], item_card_bottom_right[1], 0)
    lines.addTwoPointRectangle(p1, p2)
    extrudes.addSimple(sketch.profiles.item(0),
                       adsk.core.ValueInput.createByReal(-plate_extrude_distance),
                       adsk.fusion.FeatureOperations.JoinFeatureOperation)

    # Create & extrude the text

    sketch_texts = sketch.sketchTexts
    text_height_cm = 0.8 # font height
    side_padding_cm = 0.4

    top1 = -2.0 * mm
    baseline1 = top1 - text_height_cm
    top2 = baseline1 - (text_height_cm/2)
    baseline2 = top2 - text_height_cm

    start = - side_padding_cm - grid_margin
    end = grid_size + grid_margin - side_padding_cm

    name_text_p1 = adsk.core.Point3D.create(start, baseline1, 0)
    name_text_p2 = adsk.core.Point3D.create(end, top1, 0)
    name_text_input = sketch_texts.createInput2(name, text_height_cm)
    name_text_input.setAsMultiLine(name_text_p1,  # corner
                              name_text_p2,  # diagonal
                              adsk.core.HorizontalAlignments.RightHorizontalAlignment,
                              adsk.core.VerticalAlignments.BottomVerticalAlignment,
                              0)  # characterSpacing
    name_text_input.isHorizontalFlip = True
    name_text_input.textStyle = adsk.fusion.TextStyles.TextStyleBold
    name_text_obj = sketch_texts.add(name_text_input)

    info_text_p1 = adsk.core.Point3D.create(start, baseline2, 0)
    info_text_p2 = adsk.core.Point3D.create(end, top2, 0)
    info_text_input = sketch_texts.createInput2("github.com/\ndleppik/\nFusionBloomFilter", 0.5)
    info_text_input.setAsMultiLine(info_text_p1,  # corner
                                   info_text_p2,  # diagonal
                                   adsk.core.HorizontalAlignments.RightHorizontalAlignment,
                                   adsk.core.VerticalAlignments.TopVerticalAlignment,
                                   0)  # characterSpacing
    info_text_input.textStyle = adsk.fusion.TextStyles.TextStyleBold
    info_text_input.isHorizontalFlip = True
    info_text_obj = sketch_texts.add(info_text_input)

    extrudes.addSimple(name_text_obj,
                       adsk.core.ValueInput.createByReal(-1 * mm - plate_extrude_distance),
                       adsk.fusion.FeatureOperations.JoinFeatureOperation)

    extrudes.addSimple(info_text_obj,
                       adsk.core.ValueInput.createByReal(-1 * mm - plate_extrude_distance),
                       adsk.fusion.FeatureOperations.JoinFeatureOperation)

def draw_bloom_text(name: str, component, plane):
    global grid_spacing, pixel_size, grid_size, grid_margin, pixel_height

    sketches = component.sketches
    sketch = sketches.add(plane)

    sketch_texts = sketch.sketchTexts
    text_height_cm = 0.8
    secondary_text_height_cm = 0.6
    side_padding_cm = 0.4
    font_descent_cm = text_height_cm / 2.0
    full_text_height = grid_margin + font_descent_cm
    start = - side_padding_cm - grid_margin
    end = grid_size + grid_margin - side_padding_cm

    # Lines are listed in reverse order because the top line
    # sits on the bottom line

    line_2_start = grid_size + grid_margin
    line_2_end = line_2_start + text_height_cm
    line_1_start = line_2_end + font_descent_cm
    line_2_end = line_1_start + text_height_cm
    
    line_2_p1 = adsk.core.Point3D.create(start, line_2_start + font_descent_cm, 0)
    line_2_p2 = adsk.core.Point3D.create(end, line_2_end, 0)
    line_1_p1 = adsk.core.Point3D.create(start, line_1_start + font_descent_cm, 0)
    line_1_p2 = adsk.core.Point3D.create(end, line_2_end, 0)

    description_input = sketch_texts.createInput2("Bloom Filter", secondary_text_height_cm)
    description_input.setAsMultiLine(line_1_p1,  # corner
                                     line_1_p2,  # diagonal
                                     adsk.core.HorizontalAlignments.RightHorizontalAlignment,
                                     adsk.core.VerticalAlignments.BottomVerticalAlignment,
                                     0)  # characterSpacing
    description_input.isHorizontalFlip = True
    description_text = sketch_texts.add(description_input)


    name_input = sketch_texts.createInput2(name, text_height_cm)
    name_input.setAsMultiLine(line_2_p1,  # corner
                              line_2_p2,  # diagonal
                              adsk.core.HorizontalAlignments.RightHorizontalAlignment,
                              adsk.core.VerticalAlignments.BottomVerticalAlignment,
                              0)  # characterSpacing
    name_input.isHorizontalFlip = True
    name_input.textStyle = adsk.fusion.TextStyles.TextStyleBold
    name_text = sketch_texts.add(name_input)

    extrudes = component.features.extrudeFeatures
    extrudes.addSimple(name_text,
                       adsk.core.ValueInput.createByReal(-1 * mm),
                       adsk.fusion.FeatureOperations.JoinFeatureOperation)
    extrudes.addSimple(description_text,
                       adsk.core.ValueInput.createByReal(-1 * mm),
                       adsk.fusion.FeatureOperations.JoinFeatureOperation)

#
# Main
#

def run(context):
    global _app, _ui
    try:
        # Get the application and design
        app = adsk.core.Application.get()
        ui = app.userInterface
        _app = app
        _ui = ui

        commandDefinitions = ui.commandDefinitions
        # check the command exists or not
        cmdDef = commandDefinitions.itemById('BloomCmd')
        if not cmdDef:
            cmdDef = commandDefinitions.addButtonDefinition('BloomCmd',
                                                            'Create Bloom Filter',
                                                            'Create a Bloom filter.')

        on_command_created = BloomCommandCreatedHandler()
        cmdDef.commandCreated.add(on_command_created)
        # keep the handler referenced beyond this function
        _handlers.append(on_command_created)
        inputs = adsk.core.NamedValues.create()
        cmdDef.execute(inputs)

        # prevent this module from being terminate when the script returns, because we are waiting for event handlers to fire
        adsk.autoTerminate(False)

    except Exception as e:
        # Error handling
        if app:
            ui = app.userInterface
            ui.messageBox(f'Failed:\n{str(e)}')