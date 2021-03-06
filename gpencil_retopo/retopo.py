# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

import bpy
from math import radians
from mathutils.geometry import intersect_point_line, intersect_line_line


# gather initial data and prepare for retopologising
def initialise(context):
    scene = context.scene
    obj = context.object

    gp = None
    if obj:
        gp = obj.grease_pencil
    if not gp:
        gp = scene.grease_pencil

    if gp:
        bpy.ops.object.mode_set(mode='OBJECT')

    return(scene, gp)


def get_hub(co, _hubs, EPS_SPLINE):

    if 1:
        for hub in _hubs.values():
            if (hub.co - co).length < EPS_SPLINE:
                return hub

        key = co.to_tuple(3)
        hub = _hubs[key] = Hub(co, key, len(_hubs))
        return hub
    else:
        pass

        '''
        key = co.to_tuple(3)
        try:
            return _hubs[key]
        except:
            hub = _hubs[key] = Hub(co, key, len(_hubs))
            return hub
        '''


class Hub(object):
    __slots__ = "co", "key", "index", "links"

    def __init__(self, co, key, index):
        self.co = co.copy()
        self.key = key
        self.index = index
        self.links = []

    def get_weight(self):
        f = 0.0

        for hub_other in self.links:
            f += (self.co - hub_other.co).length

    def replace(self, other):
        for hub in self.links:
            try:
                hub.links.remove(self)
            except:
                pass
            if other not in hub.links:
                hub.links.append(other)

    def dist(self, other):
        return (self.co - other.co).length

    def calc_faces(self, hub_ls):
        faces = []
        # first tris
        for l_a in self.links:
            for l_b in l_a.links:
                if l_b is not self and l_b in self.links:
                    # will give duplicates
                    faces.append((self.index, l_a.index, l_b.index))

        # now quads, check which links share 2 different verts directly
        def validate_quad(face):
            if len(set(face)) != len(face):
                return False
            if hub_ls[face[0]] in hub_ls[face[2]].links:
                return False
            if hub_ls[face[2]] in hub_ls[face[0]].links:
                return False

            if hub_ls[face[1]] in hub_ls[face[3]].links:
                return False
            if hub_ls[face[3]] in hub_ls[face[1]].links:
                return False

            return True

        for i, l_a in enumerate(self.links):
            links_a = {l.index for l in l_a.links}
            for j in range(i):
                l_b = self.links[j]

                links_b = {l.index for l in l_b.links}

                isect = links_a.intersection(links_b)
                if len(isect) == 2:
                    isect = list(isect)

                    # check there are no diagonal lines
                    face = (isect[0], l_a.index, isect[1], l_b.index)
                    if validate_quad(face):

                        faces.append(face)

        return faces


class BBox(object):
    __slots__ = "xmin", "ymin", "zmin", "xmax", "ymax", "zmax"

    def __init__(self):
        self.xmin = self.ymin = self.zmin = 100000000.0
        self.xmax = self.ymax = self.zmax = -100000000.0

    @property
    def xdim(self):
        return self.xmax - self.xmin

    @property
    def ydim(self):
        return self.ymax - self.ymin

    @property
    def zdim(self):
        return self.zmax - self.zmin

    def calc(self, points):
        xmin = ymin = zmin = 100000000.0
        xmax = ymax = zmax = -100000000.0

        for pt in points:
            x, y, z = pt
            if x < xmin:
                xmin = x
            if y < ymin:
                ymin = y
            if z < zmin:
                zmin = z

            if x > xmax:
                xmax = x
            if y > ymax:
                ymax = y
            if z > zmax:
                zmax = z

        self.xmin, self.ymin, self.zmin = xmin, ymin, zmin
        self.xmax, self.ymax, self.zmax = xmax, ymax, zmax

    def xsect(self, other, margin=0.0):
        if margin == 0.0:
            if self.xmax < other.xmin:
                return False
            if self.ymax < other.ymin:
                return False
            if self.zmax < other.zmin:
                return False

            if self.xmin > other.xmax:
                return False
            if self.ymin > other.ymax:
                return False
            if self.zmin > other.zmax:
                return False

        else:
            xmargin = ((self.xdim + other.xdim) / 2.0) * margin
            ymargin = ((self.ydim + other.ydim) / 2.0) * margin
            zmargin = ((self.zdim + other.zdim) / 2.0) * margin

            if self.xmax < other.xmin - xmargin:
                return False
            if self.ymax < other.ymin - ymargin:
                return False
            if self.zmax < other.zmin - zmargin:
                return False

            if self.xmin > other.xmax + xmargin:
                return False
            if self.ymin > other.ymax + ymargin:
                return False
            if self.zmin > other.zmax + zmargin:
                return False
        return True

    def __iadd__(self, other):
        self.xmin = min(self.xmin, other.xmin)
        self.ymin = min(self.ymin, other.ymin)
        self.zmin = min(self.zmin, other.zmin)

        self.xmax = max(self.xmax, other.xmax)
        self.ymax = max(self.ymax, other.ymax)
        self.zmax = max(self.zmax, other.zmax)
        return self


class Spline(object):
    __slots__ = "points", "hubs", "closed", "length", "bb"

    def __init__(self, points, precision):
        self.points = points
        self.hubs = []
        self.calc_length()
        self.closed = self.calc_closed(precision)
        self.bb = BBox()
        self.bb.calc(points)

    def calc_length(self):
        # calc length
        f = 0.0
        co_prev = self.points[0]
        for co in self.points[1:]:
            f += (co - co_prev).length
            co_prev = co
        self.length = f

    def calc_closed(self, precision):
        return (self.points[0] - self.points[-1]).length < (self.length / precision)

    def link(self):
        if len(self.hubs) < 2:
            return

        edges = list(set([i for i, hub in self.hubs]))
        edges.sort()

        edges_order = {}
        for i in edges:
            edges_order[i] = []

        # self.hubs.sort()
        for i, hub in self.hubs:
            edges_order[i].append(hub)

        hubs_order = []
        for i in edges:
            ls = edges_order[i]
            edge_start = self.points[i]
            ls.sort(key=lambda hub: (hub.co - edge_start).length)
            hubs_order.extend(ls)

        # Now we have the order, connect the hubs
        hub_prev = hubs_order[0]

        for hub in hubs_order[1:]:
            hub.links.append(hub_prev)
            hub_prev.links.append(hub)
            hub_prev = hub

        if self.closed:
            hubs_order[0].links.append(hubs_order[-1])
            hubs_order[-1].links.append(hubs_order[0])


def get_points(stroke):
    return [point.co.copy() for point in stroke.points]


def get_splines(gp, precision):
    l = gp.layers.active
    if l:
        frame = l.active_frame
        return [Spline(get_points(stroke), precision) for stroke in frame.strokes if len(stroke.points) > 1]
    else:
        return []


def xsect_spline(sp_a, sp_b, _hubs, precision):
    pt_a_prev = pt_b_prev = None
    EPS_SPLINE = min(sp_a.length, sp_b.length) / precision
    pt_a_prev = sp_a.points[0]
    for a, pt_a in enumerate(sp_a.points[1:]):
        pt_b_prev = sp_b.points[0]
        for b, pt_b in enumerate(sp_b.points[1:]):

            # Now we have 2 edges
            # print(pt_a, pt_a_prev, pt_b, pt_b_prev)
            xsect = intersect_line_line(pt_a, pt_a_prev, pt_b, pt_b_prev)
            if xsect is not None:
                if (xsect[0] - xsect[1]).length <= EPS_SPLINE:
                    f = intersect_point_line(xsect[1], pt_a, pt_a_prev)[1]
                    # if f >= 0.0-EPS_SPLINE and f <= 1.0+EPS_SPLINE:
                        # for some reason doesnt work so well, same below
                    if f >= 0.0 and f <= 1.0:
                        f = intersect_point_line(xsect[0], pt_b, pt_b_prev)[1]
                        # if f >= 0.0-EPS_SPLINE and f <= 1.0+EPS_SPLINE:
                        if f >= 0.0 and f <= 1.0:
                            # This wont happen often
                            co = xsect[0].lerp(xsect[1], 0.5)
                            hub = get_hub(co, _hubs, EPS_SPLINE)

                            sp_a.hubs.append((a, hub))
                            sp_b.hubs.append((b, hub))

            pt_b_prev = pt_b

        pt_a_prev = pt_a


def connect_splines(splines, precision):
    HASH_PREC = 8
    ANG_LIMIT = radians(25.0)  # limit for joining splines into 1

    def sort_pair(a, b):
        if a < b:
            return a, b
        else:
            return b, a

    #def test_join(p1a, p1b, p2a, p2b, length_average):
    def test_join(s1, s2, dir1, dir2, length_average):
        if dir1 is False:
            p1a = s1.points[0]
            p1b = s1.points[1]
        else:
            p1a = s1.points[-1]
            p1b = s1.points[-2]

        if dir2 is False:
            p2a = s2.points[0]
            p2b = s2.points[1]
        else:
            p2a = s2.points[-1]
            p2b = s2.points[-2]

        v1 = p1a - p1b
        v2 = p2b - p2a

        if v1.angle(v2, ANG_LIMIT) >= ANG_LIMIT:
            return False

        # trim s2, allow overlapping line.
        v2_test_1 = p2b - p2a
        if dir2 is False:
            i = 2
            while (p2b - p1a).length < (p2a - p1a).length and i < len(s2.points):
                p2a = p2b
                p2b = s2.points[i]
                i += 1
        else:
            i = -3
            while (p2b - p1a).length < (p2a - p1a).length and -i <= len(s2.points):
                p2a = p2b
                p2b = s2.points[i]
                i -= 1

        # when trimming did we we turn a corner?
        v2_test_2 = p2b - p2a
        if v2_test_1.angle(v2_test_2, ANG_LIMIT) >= ANG_LIMIT:
            return False
        del v2_test_1
        del v2_test_2
        # end trimming

        # compare length between tips
        if (p1a - p2a).length > (length_average / precision):
            return False

        # print("joining!")
        return True

    # lazy, hash the points that have been compared.
    comparisons = set()

    do_join = True
    while do_join:
        do_join = False
        for i, s1 in enumerate(splines):
            key1a = s1.points[0].to_tuple(HASH_PREC)
            key1b = s1.points[-1].to_tuple(HASH_PREC)

            for j, s2 in enumerate(splines):
                if s1 is s2:
                    continue

                length_average = min(s1.length, s2.length)

                key2a = s2.points[0].to_tuple(HASH_PREC)
                key2b = s2.points[-1].to_tuple(HASH_PREC)

                # there are 4 ways this may be joined
                key_pair = sort_pair(key1a, key2a)
                if key_pair not in comparisons:
                    comparisons.add(key_pair)
                    if test_join(s1, s2, False, False, length_average):
                        s1.points[:0] = reversed(s2.points)
                        s1.bb += s2.bb
                        s1.calc_length()
                        del splines[j]
                        do_join = True
                        break

                key_pair = sort_pair(key1a, key2b)
                if key_pair not in comparisons:
                    comparisons.add(key_pair)
                    if test_join(s1, s2, False, True, length_average):
                        s1.points[:0] = s2.points
                        s1.bb += s2.bb
                        s1.calc_length()
                        del splines[j]
                        do_join = True
                        break

                key_pair = sort_pair(key1b, key2b)
                if key_pair not in comparisons:
                    comparisons.add(key_pair)
                    if test_join(s1, s2, True, True, length_average):
                        s1.points += list(reversed(s2.points))
                        s1.bb += s2.bb
                        s1.calc_length()
                        del splines[j]
                        do_join = True
                        break

                key_pair = sort_pair(key1b, key2a)
                if key_pair not in comparisons:
                    comparisons.add(key_pair)
                    if test_join(s1, s2, True, False, length_average):
                        s1.points += s2.points
                        s1.bb += s2.bb
                        s1.calc_length()
                        del splines[j]
                        do_join = True
                        break

            if do_join:
                break


def calculate(gp, precision):
    # note, this precision is for closed lines, it could be a different arg.
    splines = get_splines(gp, precision)

    # spline endpoints may be co-linear, join these into single splines
    connect_splines(splines, precision)

    _hubs = {}

    for i, sp in enumerate(splines):
        for j, sp_other in enumerate(splines):
            if j <= i:
                continue

            if sp.bb.xsect(sp_other.bb, margin=0.1):
                xsect_spline(sp, sp_other, _hubs, precision)

    for sp in splines:
        sp.link()

    # remove these
    hubs_ls = [hub for hub in _hubs.values() if hub.index != -1]

    _hubs.clear()
    _hubs = None

    for i, hub in enumerate(hubs_ls):
        hub.index = i

    # Now we have connected hubs, write all edges!
    def order(i1, i2):
        if i1 > i2:
            return i2, i1
        return i1, i2

    edges = {}

    for hub in hubs_ls:
        i1 = hub.index
        for hub_other in hub.links:
            i2 = hub_other.index
            edges[order(i1, i2)] = None

    verts = []
    edges = edges.keys()
    faces = []

    for hub in hubs_ls:
        verts.append(hub.co)
        faces.extend(hub.calc_faces(hubs_ls))

    # remove double faces
    faces = dict([(tuple(sorted(f)), f) for f in faces]).values()

    mesh = bpy.data.meshes.new("Retopo")
    mesh.from_pydata(verts, [], faces)

    scene = bpy.context.scene
    mesh.update()
    obj_new = bpy.data.objects.new(name="Retopo", object_data=mesh)
    scene.objects.link(obj_new)

    return obj_new
