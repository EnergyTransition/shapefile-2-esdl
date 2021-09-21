#  This work is based on original code developed and copyrighted by TNO 2021.
#  Subsequent contributions are licensed to you by the developers of such code and are
#  made available to the Project under one or several contributor license agreements.
#
#  This work is licensed to you under the Apache License, Version 2.0.
#  You may obtain a copy of the license at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Contributors:
#      TNO         - Initial implementation
#  Manager:
#      TNO

from osgeo import gdal      # required by Fiona
import fiona
from shapely.geometry import shape, Point, LineString, mapping
from uuid import uuid4
import copy
import math
from esdl import esdl
from esdl.esdl_handler import EnergySystemHandler
from shape import Shape

SHAPEFILE_LINES_FILENAME = "./data/example_network.shp"
ESDL_OUTPUT_FILENAME = "./output/pipes.esdl"
BUFFER_JOINTS_OUTPUT_FILENAME = "./output/points_buffer.shp"
T_JOINTS_OUTPUT_FILENAME = "./output/t_joint_points.shp"

BUFFER_POINTS_TOUCHING = 0.02               # toleration for detecting touching lines
ANGLE_DIFFERENCE_SIMPLIFY = 5               # simplify if angle difference less than 5 degrees
ANGLE_DIFFERENT_DIRECTION = 5               # assume other direction if angle is bigger than ...
SIMPLIFY_LINE_SEGMENTS = True               # simplify network by joining line segments that run in same direction
SHAPEFILE_PIPE_DIAMETER_KEY = 'PIJPDIA'     # attribute name in the shapefile of the pipe diameter
JOIN_PIPES_WITH_DIFFERENT_SIZE = False      # adds a 'adapter' joint when pipe diameter changes


def get_line_segments(curve: LineString):
    """
    Splits a LineString with 2 or more coordinates into a list of line segments

    :param curve: Input line (Shapely LineString) that will be split into segments
    :return: list of LineStrings where each item contains only two coordinates
    """
    return list(map(LineString, zip(curve.coords[:-1], curve.coords[1:])))


def get_split_lines(lines_shapefile):
    """
    Creates a list of line segments (a straight piece of line with two coordinates (the end points of the line) based
    on information coming from a shapefile

    :param lines_shapefile: lines read from a shapefile
    :return: list of line segments
    """
    lines = dict()
    for line_sh in lines_shapefile:
        line = shape(line_sh['geometry'])
        line_segments = get_line_segments(line)
        for ls in line_segments:
            lid = str(uuid4())
            lines[lid] = {
                'id': lid,
                'shape': ls,
                'line_sh': line_sh,
                'points': list()
            }

    return lines


def split_line_segment_at_point(line_segment, p, points, lines):
    """
    Splits a line_segment into two pieces at the location of point p, line_a and line_b. Basically line_segment will be
    shortened (the shorter version is line_a) and line_b will be added to the list of lines.
    Note: Point p doesn't need to be exactly located at the line segment

    :param line_segment: the line segment that will be splitted.
    :param p: the point at which the line segment will be splitted.
    :param points: list of all end points of line segments
    :param lines:  list of all line segments
    :return: None
    """
    line_a_end_point_id = str(uuid4())
    line_b_start_point_id = str(uuid4())
    line_b_id = str(uuid4())

    line_a_end_point = copy.deepcopy(p)
    line_a_end_point['id'] = line_a_end_point_id
    line_a_end_point['type'] = 'end'
    line_a_end_point['line_id'] = line_segment['id']
    line_a_end_point['intersecting_points'] = [p['id'], line_b_start_point_id]
    line_a_end_point['t_joint_type'] = 'end'

    line_b_start_point = copy.deepcopy(p)
    line_b_start_point['id'] = line_b_start_point_id
    line_b_start_point['type'] = 'start'
    line_b_start_point['line_id'] = line_b_id
    line_b_start_point['intersecting_points'] = [p['id'], line_a_end_point_id]
    line_b_start_point['t_joint_type'] = 'end'

    line_b = {
        'id': line_b_id,
        'shape': LineString([line_b_start_point['shape'].coords[0], line_segment['points'][1]['shape'].coords[0]]),
        'line_sh': line_segment['line_sh'],
        'points': [line_b_start_point, line_segment['points'][1]],
    }
    line_b['points'][1]['line_id'] = line_b_id

    line_segment['points'][1] = line_a_end_point
    line_segment['shape'] = LineString([line_segment['points'][0]['shape'].coords[0], line_a_end_point['shape'].coords[0]])

    points[line_a_end_point_id] = line_a_end_point
    points[line_b_start_point_id] = line_b_start_point
    lines[line_b_id] = line_b

    p['t_joint_type'] = 'end'
    p['intersecting_points'] = [line_a_end_point_id, line_b_start_point_id]


def angle_line_segments(l1, l2):
    """
    Calculates the angle between two Shapely LineStrings in degrees.

    :param l1: first linestring
    :param l2: second linestring
    :return: angle in degrees
    """
    dydx_l1 = (l1.coords[1][1]-l1.coords[0][1]) / (l1.coords[1][0]-l1.coords[0][0])
    dydx_l2 = (l2.coords[1][1]-l2.coords[0][1]) / (l2.coords[1][0]-l2.coords[0][0])
    # print (math.atan(dydx_l1) - math.atan(dydx_l2)) * 180 / math.pi
    return (math.atan(dydx_l1) - math.atan(dydx_l2)) * 180 / math.pi


def reverse_coordinates_line_segment(line_shape):
    """
    Reverses the coordinates of a line segment (Shapely LineString with only 2 coordinates)

    :param line_shape: the line segment (a Shapely LineString) that needs to be reversed
    :return: the reversed line segment
    """
    return LineString([line_shape.coords[1], line_shape.coords[0]])


def angle_line_segments_from_points(p1, p2, lines):
    """
    Calculates the angle between two line segments from two points

    :param p1: point on the first line segment
    :param p2: point on the second line segment
    :param lines: list of all line segments
    :return: angle between the two line segments in degrees
    """
    line_of_p1_shape = lines[p1['line_id']]['shape']
    line_of_p2_shape = lines[p2['line_id']]['shape']

    if p1['type'] == 'end':
        line_of_p1_shape = reverse_coordinates_line_segment(line_of_p1_shape)
    if p2['type'] == 'end':
        line_of_p2_shape = reverse_coordinates_line_segment(line_of_p2_shape)
        
    return angle_line_segments(line_of_p1_shape, line_of_p2_shape)


def check_angles(p, points, lines):
    """
    Checks the angles between all line segments that start at a certain point. It detects different lines that move away
    from a point in exactly the same direction (basically overlapping pipes).

    :param p: the point for which the angles of line segments will be calculted
    :param points: list of all end points of line segments
    :param lines: list of all line segments
    :return: true if all angles are larger than ANGLE_DIFFERENT_DIRECTION
    """
    angles = list()
    for p_intersecting_idx in p['intersecting_points']:
        p_intersecting = points[p_intersecting_idx]
        angles.append(angle_line_segments_from_points(p, p_intersecting, lines))

    # TODO: implement support for more than 3 lines at an intersecting point
    return abs(angles[0] - angles[1]) > ANGLE_DIFFERENT_DIRECTION


def add_or_replace_points(res_line_points, p):
    """
    Builds up the resulting line. The point p is added to the list if the line segment is going in another direction
    or point p is replacing the last point of the line if the line segment is actually a direct continuation of the
    last added line segment.

    If SIMPLIFY_LINE_SEGMENTS is set to True, line segments of which the angle is smaller
    than ANGLE_DIFFERENT_DIRECTION are joined (treated as one) to simplify the network and reduce the line size. The
    creator of the shapefile usually manually draws these lines in approximately the same direction.

    :param res_line_points: list of points for one resulting line
    :param p: point to be added to the line
    :return: None
    """
    if len(res_line_points) > 1 and SIMPLIFY_LINE_SEGMENTS:
        l1 = LineString([res_line_points[-2], res_line_points[-1]])
        l2 = LineString([res_line_points[-1], p])
        if abs(angle_line_segments(l1, l2)) < ANGLE_DIFFERENT_DIRECTION:
            res_line_points.pop()
    res_line_points.append(p)


def find_line(point, points, lines, res_lines, res_line, adapters):
    """
    Iterates over the line segments to constuct a connected line. Ends at either the line endpoint, or at a T joint
    location or optionally at a so-called 'adapter' (where line size changes) based on the value of
    CONNECT_PIPES_WITH_DIFFERENT_SIZE

    :param point: point to start from when building up the connected line
    :param points: list of all end points of line segments
    :param lines: list of all line segments
    :param res_lines: collection of detected 'connected' line segments
    :param res_line: start of to be constructed line
    :param adapters: collection of so-called 'adapters' that connect two pipe segments with different DN sizes
    :return: None
    """
    line = lines[point['line_id']]
    if point['type'] == 'start':
        other_point = line['points'][1]
        assert(other_point['type'] == 'end')
    elif point['type'] == 'end':
        other_point = line['points'][0]
        assert(other_point['type'] == 'start')
    else:
        raise Exception('point has other type than start or end')

    add_or_replace_points(res_line['points'], other_point['shape'])
    point['processed'] = True
    other_point['processed'] = True

    number_of_intersected_points = len(other_point['intersecting_points'])
    if number_of_intersected_points == 0:
        # print(f"End of line reached - {other_point['t_joint_type']} - {len(res_line['points'])} points")
        res_line['end'] = {'type': 'end point'}
        res_lines.append(res_line)
    elif number_of_intersected_points == 1:
        if not JOIN_PIPES_WITH_DIFFERENT_SIZE:
            current_pipe_diameter = line['line_sh']['properties'][SHAPEFILE_PIPE_DIAMETER_KEY]
            next_pipe = lines[points[other_point['intersecting_points'][0]]['line_id']]
            next_pipe_diameter = next_pipe['line_sh']['properties'][SHAPEFILE_PIPE_DIAMETER_KEY]
            if current_pipe_diameter != next_pipe_diameter:
                print(f"Connect {current_pipe_diameter} to {next_pipe_diameter}")
                adapter_nr = len(adapters) + 1
                adapter = {'id': adapter_nr, 'shape': other_point['shape']}
                adapters.append(adapter)
                res_line['end'] = {'type': 'adapter', 'nr': adapter_nr}  # Pipe to pipe connection (with different sizes)
                res_lines.append(res_line)
                res_line = {
                    'points': [points[other_point['intersecting_points'][0]]['shape']],
                    'start': {'type': 'adapter', 'nr': adapter_nr},
                    'end': 0,
                    'diameter': next_pipe_diameter
                }
            find_line(points[other_point['intersecting_points'][0]], points, lines, res_lines, res_line, adapters)
        else:
            find_line(points[other_point['intersecting_points'][0]], points, lines, res_lines, res_line, adapters)
    elif number_of_intersected_points > 1:
        # print(f"Line ended at T-joint {other_point['t_joint_nr']} - {len(res_line['points'])} points")
        res_line['end'] = {'type': 't-joint', 'nr': other_point['t_joint_nr']}
        res_lines.append(res_line)
        process_t_joint(other_point, points, lines, res_lines, adapters)


def process_t_joint(start_t_joint_point, points, lines, res_lines, adapters):
    """
    Processes a T joint location. Assumes the leg of start_t_joint_point has been processed already. Iterates over all
    connected line segments (that form the T joint) and starts discovering connected line segments that move away from
    this T joint

    :param start_t_joint_point: T joint to process
    :param points: list of all end points of line segments
    :param lines: list of all line segments
    :param res_lines: collection of detected 'connected' line segments
    :param adapters: collection of so-called 'adapters' that connect two pipe segments with different DN sizes
    :return:
    """
    # print(start_point['t_joint_nr'])
    # process all other 'legs' of the t-joint
    for pid in start_t_joint_point['intersecting_points']:
        p = points[pid]
        if not p['processed']:
            # start a new line of connected line segments with equal sizes
            pipe_diameter = lines[p['line_id']]['line_sh']['properties'][SHAPEFILE_PIPE_DIAMETER_KEY]
            res_line = {
                'points': [p['shape']],
                'start': {'type': 't-joint', 'nr': p['t_joint_nr']},
                'end': 0,
                'diameter': pipe_diameter
            }
            find_line(p, points, lines, res_lines, res_line, adapters)


def find_all_lines(start_t_joint_point, points, lines, res_lines, adapters):
    """
    Start of the algorithm to extract the topology information from the shapefile data. The algorithm starts at one of
    the t-joint locations in the network and traverses the network until all connected lines have been processed.

    :param start_t_joint_point: T joint location to start the topology discovery
    :param points: list of all end points of line segments
    :param lines: list of all line segments
    :param res_lines: collection of detected 'connected' line segments
    :param adapters: collection of so-called 'adapters' that connect two pipe segments with different DN sizes
    :return: None
    """
    if not start_t_joint_point['processed']:
        # process current/first 'leg' of the t-joint
        pipe_diameter = lines[start_t_joint_point['line_id']]['line_sh']['properties'][SHAPEFILE_PIPE_DIAMETER_KEY]
        res_line = {
            'points': [start_t_joint_point['shape']],
            'start': {'type': 't-joint', 'nr': start_t_joint_point['t_joint_nr']},
            'end': 0,
            'diameter': pipe_diameter
        }
        # iterate over all line segments until we find the end of this line (or a t-joint, or an adapter)
        find_line(start_t_joint_point, points, lines, res_lines, res_line, adapters)

    # process t-joint (beasically the other 'legs')
    process_t_joint(start_t_joint_point, points, lines, res_lines, adapters)


def check_points_lines(points, lines):
    """
    Function to check the validity of the points and lines collections. Only required for development / debugging. When
    the algorithm functions properly, all assertions should pass. It could however trigger an error for unexpected
    input.

    :param points: list of all end points of line segments
    :param lines: list of all line segments
    :return: None
    """
    for lid, l in lines.items():
        # Check if all points of the line also refer to the line
        for lp in l['points']:
            # if lp['line_id'] != l['id']:
            #     print(f"line id: {l['id']}, line point line id: {lp['line_id']}")
            assert(lp['line_id'] == l['id'])

        # Check if all lines have a start and an end
        assert(l['points'][0]['type'] != l['points'][1]['type'])

    # Check if all points that refer to a line are also part of that line
    for pid, p in points.items():
        line = lines[p['line_id']]
        assert(p in line['points'])


def add_joint_to_area(area, name, point_shape):
    """
    Adds an ESDL joint to an area with a given name and a given location

    :param area: the ESDL area to which the joint will be added
    :param name: name of the joint
    :param point_shape: the location of the joint (Shapely Point)
    :return: the ESDL joint that was added to the area
    """
    esdl_joint = esdl.Joint(id=str(uuid4()), name=name)
    point_shp = Shape.transform_crs(Shape.create(point_shape), 'EPSG:28992')
    esdl_joint.geometry = point_shp.get_esdl()
    esdl_joint.port.append(esdl.InPort(id=str(uuid4()), name='InPort'))
    esdl_joint.port.append(esdl.OutPort(id=str(uuid4()), name='OutPort'))
    area.asset.append(esdl_joint)
    return esdl_joint


if __name__ == "__main__":
    # =============================================================================================================
    #  Read shapefile and build up list of line segments and list of points (end points of these line segments)
    # =============================================================================================================
    print("=== Schema of shapefile")
    lines_shapefile = fiona.open(SHAPEFILE_LINES_FILENAME)
    print(lines_shapefile.schema)
    print("=== CRS of shapefile")
    print(lines_shapefile.crs)

    print("=== Split all lines in individual line segments")
    lines = get_split_lines(lines_shapefile)

    # Build dictionary with all points (start, middle and end points of linestrings)
    print("=== Find all end points of line segments")
    points = dict()
    for lid, l in lines.items():
        line_shapely = l['shape']
        coords = line_shapely.coords
        for pidx in range(len(coords)):
            pid = str(uuid4())
            point = {
                'id': pid,
                'shape': Point(coords[pidx]),
                'type': 'middle',
                'line_id': lid,
                'intersecting_points': list(),
                't_joint_type': 'none',
                't_joint_nr': 0,
                'processed': False,
            }
            if pidx == 0:
                point['type'] = 'start'
            elif pidx == len(coords)-1:
                point['type'] = 'end'
            else:
                raise Exception("Not all lines have been split into line segments")
            points[pid] = point
            l['points'].append(point)

    # =============================================================================================================
    #  Iterate through the list of points and find out which points are 'touching'
    # =============================================================================================================
    print("=== Find 'touching' points")
    for pid1, p1 in points.items():
        for pid2, p2 in points.items():
            if pid1 != pid2:            # points are not the same
                # if p1['shape'].buffer(BUFFER_POINTS_TOUCHING).intersects(p2['shape'].buffer(BUFFER_POINTS_TOUCHING)):
                if p1['shape'].distance(p2['shape']) < BUFFER_POINTS_TOUCHING:
                    if pid2 not in points[pid1]['intersecting_points']:
                        points[pid1]['intersecting_points'].append(pid2)
                    if pid1 not in points[pid2]['intersecting_points']:
                        points[pid2]['intersecting_points'].append(pid1)

    # =============================================================================================================
    #  Find T joint locations
    # =============================================================================================================
    print("=== Find T-joints (at middle of line)")
    t_joint_points = list()
    t_joint_nr = 0
    for pid, p in points.items():
        for lid, l in lines.items():
            if p['line_id'] != lid:     # point does not belong to this line
                # if p['shape'].buffer(BUFFER_POINTS_TOUCHING).intersects(l['shape']):
                if p['shape'].distance(l['shape']) < BUFFER_POINTS_TOUCHING:
                    if len(p['intersecting_points']) == 0:      # no other intersecting points
                        # print(f"point intersects at middle of line - {lid}")
                        p['t_joint_type'] = 'middle'
                        t_joint_nr = t_joint_nr + 1
                        p['t_joint_nr'] = t_joint_nr
                        t_joint_points.append({
                            'nr': t_joint_nr,
                            'point': p,
                            'lid': lid,
                            'shape': p['shape'],
                            'intersecting_points': len(p['intersecting_points'])
                        })

    num_t_joints_middle_of_line = len(t_joint_points)
    print(f"{num_t_joints_middle_of_line} points found where the intersection occurs somewhere at the middle of a line")
    print("=== Splitting these lines")
    for tj_middle in t_joint_points:
        split_line_segment_at_point(lines[tj_middle['lid']], tj_middle['point'], points, lines)

    print("=== Check data structures consistancy")
    check_points_lines(points, lines)

    print("=== Find points that have more than one 'touching' point - add as T-joint")
    for pid, p in points.items():
        if len(p['intersecting_points']) == 2 and p['t_joint_type'] == 'none':
            # print("point has 2 other intersecting points")

            t_joint_nr = t_joint_nr + 1
            p['t_joint_nr'] = t_joint_nr

            # Give all other intersecting points a 'status' such that they will not be processed again
            for ipid in p['intersecting_points']:
                ip = points[ipid]
                ip['t_joint_type'] = 'end'
                ip['t_joint_nr'] = t_joint_nr

            # The following check is not working yet, probably opposite directions are not detected
            if check_angles(p, points, lines):
                p['t_joint_type'] = 'end'
            else:
                p['t_joint_type'] = 'same angle'
                print("lines that start at point with 2 other intersecting points are not in different directions")

            t_joint_points.append({
                'nr': t_joint_nr,
                'point': p,
                'shape': p['shape'],
                'intersecting_points': len(p['intersecting_points'])
            })
        elif len(p['intersecting_points']) > 2:
            raise Exception("point has more than 2 intersecting points")

    print(f"{len(t_joint_points)-num_t_joints_middle_of_line} t-joint locations found at end points of lines")

    # =============================================================================================================
    #  Create some shapefiles for visualizing intermediate results
    # =============================================================================================================
    print("=== Create shapefile with buffers for determining connected points")
    schema = {
        'geometry': 'Polygon',
        'properties': {
            'intersecting_points': 'int',
            't_joint_type': 'str'
        },
    }
    with fiona.open(BUFFER_JOINTS_OUTPUT_FILENAME, 'w', crs=lines_shapefile.crs, driver=lines_shapefile.driver, schema=schema) as out_shapefile:
        for pk, p in points.items():
            out_shapefile.write({
                'geometry': mapping(p['shape'].buffer(BUFFER_POINTS_TOUCHING)),
                'properties': {
                    'intersecting_points': len(p['intersecting_points']),
                    't_joint_type': p['t_joint_type'],
                },
            })

    print("=== Create shapefile with T-joints")
    print(f"Number of T-joints detected: {len(t_joint_points)}")
    schema = {
        'geometry': 'Point',
        'properties': {
            'nr': 'int',
            'intersecting_points': 'int',
        },
    }
    with fiona.open(T_JOINTS_OUTPUT_FILENAME, 'w', crs=lines_shapefile.crs, driver=lines_shapefile.driver, schema=schema) as out_shapefile:
        for tp in t_joint_points:
            out_shapefile.write({
                'geometry': mapping(tp['shape']),
                'properties': {
                    'nr': tp['nr'],
                    'intersecting_points': tp['intersecting_points'],
                },
            })

    # =============================================================================================================
    #  Discover topology
    # =============================================================================================================
    res_lines = list()
    adapters = list()
    for tjp in t_joint_points:
        # print(f"Start with joint {tjp['nr']} - {tjp['point']['t_joint_type']}:")
        find_all_lines(tjp['point'], points, lines, res_lines, adapters)

    print(f"{len(res_lines)} pipes were generated from {len(lines)} shapefile pipe segments")

    # =============================================================================================================
    #  Create ESDL
    # =============================================================================================================
    print("=== Generating ESDL")
    esh = EnergySystemHandler()
    es = esh.create_empty_energy_system(name="shapefile test", es_description="", inst_title="instance", area_title="area")
    area = es.instance[0].area

    for l in res_lines:
        line_shape = LineString(l['points'])
        # print(f"Line from {l['start']} to {l['end']}: {line_shape}")

        line_shp = Shape.transform_crs(Shape.create(line_shape), 'EPSG:28992')
        # line_shp.transform_crs('EPSG:28992', from_crs='EPSG:4326')

        name = f"Pipe from {l['start']} to {l['end']} - {l['diameter']}"
        pipe = esdl.Pipe(id=str(uuid4()), name=name)
        pipe.geometry = line_shp.get_esdl()
        pipe.port.append(esdl.InPort(id=str(uuid4()), name='InPort'))
        pipe.port.append(esdl.OutPort(id=str(uuid4()), name='OutPort'))
        area.asset.append(pipe)

        # Add esdl.Joint (if required) and connect Pipe
        if l['start']['type'] == 't-joint':
            t_joint = t_joint_points[l['start']['nr']-1]
            if "ESDL_info" in t_joint:
                esdl_joint = t_joint["ESDL_info"]
            else:
                esdl_joint = add_joint_to_area(area, f"Joint {l['start']['nr']}", t_joint['shape'])
                t_joint["ESDL_info"] = esdl_joint

            pipe.port[0].connectedTo.append(esdl_joint.port[1])   # Pipe InPort <--> Joint OutPort

        if l['start']['type'] == 'adapter':
            adapter = adapters[l['start']['nr']-1]
            if "ESDL_info" in adapter:
                esdl_joint = adapter["ESDL_info"]
            else:
                esdl_joint = add_joint_to_area(area, f"Joint {l['start']['nr']}", adapter['shape'])
                adapter["ESDL_info"] = esdl_joint

            pipe.port[0].connectedTo.append(esdl_joint.port[1])   # Pipe InPort <--> Joint OutPort

        if l['end']['type'] == 't-joint':
            t_joint = t_joint_points[l['end']['nr']-1]
            if "ESDL_info" in t_joint:
                esdl_joint = t_joint["ESDL_info"]
            else:
                esdl_joint = add_joint_to_area(area, f"Joint {l['end']['nr']}", t_joint['shape'])
                t_joint["ESDL_info"] = esdl_joint

            pipe.port[1].connectedTo.append(esdl_joint.port[0])   # Pipe OutPort <--> Joint InPort

        if l['end']['type'] == 'adapter':
            adapter = adapters[l['end']['nr']-1]
            if "ESDL_info" in adapter:
                esdl_joint = adapter["ESDL_info"]
            else:
                esdl_joint = add_joint_to_area(area, f"Joint {l['end']['nr']}", adapter['shape'])
                adapter["ESDL_info"] = esdl_joint

            pipe.port[1].connectedTo.append(esdl_joint.port[0])   # Pipe OutPort <--> Joint InPort

    esh.save(ESDL_OUTPUT_FILENAME)
