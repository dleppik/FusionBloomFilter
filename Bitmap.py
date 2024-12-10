import adsk.core, adsk.fusion, traceback
import hashlib

# Global variables to keep references
_app = None
_ui = None
_handlers = []

# Grid specifications in cm
grid_line_width = 0.15
point_size = 0.3
grid_size = (point_size + grid_line_width) * 16
border_size = 0.2
bloom_height_cm = 0.4

class BloomCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            # Get the command inputs
            inputs = args.command.commandInputs
            name = inputs.itemById('nameInput').value
            paragraph = inputs.itemById('itemsInput').text

            # Get the active design and component
            design = _app.activeProduct
            component = design.activeComponent

            num_hashes = 10
            items = [s.strip() for s in paragraph.split('\n')]
            bloom = create_bloom_filter(items, num_hashes)

            draw_bloom_component(bloom, name, component)

            item_spacing = bloom_height_cm * 3
            item_height = item_spacing
            for item in items[0:2]:
                draw_hash_item(item, num_hashes, item_height, component)
                item_height = item_height + item_spacing
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
            inputs.addStringValueInput('nameInput', 'Name', 'Crops')
            inputs.addTextBoxCommandInput('itemsInput', 'Items', 'Oats\nPeas\nBeans\nBarley', 5, False)

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
    global grid_line_width, point_size, grid_size, border_size, bloom_height_cm
    occurrence = parent_component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    component = occurrence.component
    component.name = name

    sketches = component.sketches
    xy_plane = component.xYConstructionPlane
    sketch = sketches.add(xy_plane)
    draw_bloom_grid(bloom, component, sketch)

    # Draw the name
    draw_name(name, sketch)

def draw_bloom_grid(bloom, component, sketch):
    """
    Draw Bloom sketch and boxes. This must be done in a sketch with no other profiles.
    """
    global grid_line_width, point_size, grid_size, border_size, bloom_height_cm

    point_tolerance = 0.0
    full_point_size = point_size + grid_line_width

    lines = sketch.sketchCurves.sketchLines

    for grid_x in range(16):
        for grid_y in range(16):
            byte = byte_for_coordinate(grid_x, grid_y)
            if byte in bloom:
                block_x = grid_x * full_point_size
                block_y = grid_y * full_point_size

                p1_offset = grid_line_width + point_tolerance
                p1 = adsk.core.Point3D.create(block_x + p1_offset, block_y + p1_offset, 0)

                p2_offset = grid_line_width + point_size - point_tolerance
                p2 = adsk.core.Point3D.create(block_x + p2_offset, block_y + p2_offset, 0)
                lines.addTwoPointRectangle(p1, p2)

    # Draw outline and extrude
    lines.addTwoPointRectangle(
        adsk.core.Point3D.create(-border_size, -border_size, 0),
        adsk.core.Point3D.create(grid_size + border_size, grid_size + border_size, 0))
    extrudes = component.features.extrudeFeatures
    extrudes.addSimple(sketch.profiles.item(sketch.profiles.count - 1),
                       adsk.core.ValueInput.createByReal(bloom_height_cm),
                       adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

def draw_hash_item(item: str, num_hashes, height_cm: float, parent_component):
    occurrence = parent_component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    component = occurrence.component
    component.name = item

    # create plane
    planes = component.constructionPlanes
    plane_input = planes.createInput()
    offset = adsk.core.ValueInput.createByReal(height_cm)
    plane_input.setByOffset(component.xYConstructionPlane, offset)
    plane = planes.add(plane_input)

    sketches = draw_hash_sketches(item, num_hashes, plane, component)
    draw_name(item, sketches[0])


def draw_hash_sketches(item: str, num_hashes, plane, component):
    global grid_line_width, point_size, grid_size, border_size, bloom_height_cm

    point_tolerance = 0.2 / 10  # 0.2 mm tolerance
    full_point_size = point_size + grid_line_width

    sketches = component.sketches
    sketch1 = sketches.add(plane)
    lines = sketch1.sketchCurves.sketchLines

    item_hash = create_bloom_filter([item], num_hashes)

    for grid_x in range(16):
        for grid_y in range(16):
            byte = byte_for_coordinate(grid_x, grid_y)
            if byte in item_hash:
                block_x = grid_x * full_point_size
                block_y = grid_y * full_point_size

                p1_offset = grid_line_width + point_tolerance
                p1 = adsk.core.Point3D.create(block_x + p1_offset, block_y + p1_offset, 0)

                p2_offset = grid_line_width + point_size - point_tolerance
                p2 = adsk.core.Point3D.create(block_x + p2_offset, block_y + p2_offset, 0)
                lines.addTwoPointRectangle(p1, p2)

    # Extrude all profiles. It's too hard to determine which ones we want, hence doing this in a fresh sketch

    profiles_to_extrude1 = adsk.core.ObjectCollection.create()
    for prof_index in range(sketch1.profiles.count):
        profiles_to_extrude1.add(sketch1.profiles.item(prof_index))
    extrudes = component.features.extrudeFeatures
    extrudes.addSimple(profiles_to_extrude1,
                       adsk.core.ValueInput.createByReal(-bloom_height_cm), # Negative to point toward filter
                       adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

    # Draw a containing rectangle and extrude it in its own sketch in order to ignore the interior profiles

    sketch2 = sketches.add(plane)
    lines2 = sketch2.sketchCurves.sketchLines
    lines2.addTwoPointRectangle(
        adsk.core.Point3D.create(-border_size, -border_size, 0),
        adsk.core.Point3D.create(grid_size + border_size, grid_size + border_size, 0))

    extrudes.addSimple(sketch2.profiles.item(0),
                       adsk.core.ValueInput.createByReal(0.1), # Positive to preserve hash extrude length
                       adsk.fusion.FeatureOperations.JoinFeatureOperation)

    return [sketch1, sketch2]

def draw_name(name: str, sketch):
    global grid_line_width, point_size, grid_size, border_size, bloom_height_cm
    sketch_texts = sketch.sketchTexts
    text_height_cm = 0.8
    font_descent_cm = text_height_cm / 2.0
    baseline = grid_size + border_size + font_descent_cm
    top = baseline + text_height_cm
    name_text_p2 = adsk.core.Point3D.create(grid_size + border_size, top, 0)
    name_text_p1 = adsk.core.Point3D.create(-border_size, baseline, 0)
    text_input = sketch_texts.createInput2(name, text_height_cm)
    text_input.setAsMultiLine(name_text_p1,  # corner
                              name_text_p2,  # diagonal
                              adsk.core.HorizontalAlignments.RightHorizontalAlignment,
                              adsk.core.VerticalAlignments.BottomVerticalAlignment,
                              0)  # characterSpacing
    text_input.isHorizontalFlip = True
    text_input.textStyle = adsk.fusion.TextStyles.TextStyleBold
    sketch_texts.add(text_input)

#
# Bloom filter utils
#

def create_bloom_filter(entries, num_hashes = 8):
    bloom = set()
    for item in entries:
        add_to_32_bit_bloom_filter(item, num_hashes, bloom)
    return bloom

def item_in_bloom(item: str, bloom, num_hashes: int) -> bool:
    item_hash = create_bloom_filter([item], num_hashes)
    return item_hash & bloom == item_hash

def add_to_32_bit_bloom_filter(string_to_add: str, num_hashes = 8, bloom = set()):
    """
    Generate or add to a toy bloom filter. In a real bloom filter, we'd use
    a bitmap rather than a set of numbers, since the whole point is to be
    memory efficient.

    This can be called a single time to generate the sparse hash for a single item.
    """
    encoded_string = string_to_add.encode('utf-8')

    # A Bloom filter generates multiple hashes per item.
    # Since all bits are equally probable in a high-quality hash,
    # we can slice up a 265-bit hash into up to 32 1-byte hashes.
    sha256_hash = hashlib.sha256(encoded_string).digest()

    for i in range(num_hashes):
        bloom.add(sha256_hash[i])

    return set


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

        onCommandCreated = BloomCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        # keep the handler referenced beyond this function
        _handlers.append(onCommandCreated)
        inputs = adsk.core.NamedValues.create()
        cmdDef.execute(inputs)

        # prevent this module from being terminate when the script returns, because we are waiting for event handlers to fire
        adsk.autoTerminate(False)

    except Exception as e:
        # Error handling
        if app:
            ui = app.userInterface
            ui.messageBox(f'Failed:\n{str(e)}')