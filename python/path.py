import gmplot
import scrapetimetable
import datetime
import tables
from collections import OrderedDict
import math
from scipy import optimize
import matplotlib.pyplot as plt
import numpy as np

bus_ids = ['0497', '2191', '2194', '2297', '2134', '6005', '2204', '2206', '2229', '2149', '2223', '2220', '6009', '2248', '2151', '2174', '2175', '2245', '2178', '2179', '2266', '2241', '2242', '2243', '2288', '2281', '2283', '2284', '2285', '2286', '2287', '2183', '2186', '2185', '2189', '2260', '2123', '2125', '2124', '2126', '2219', '2235', '2237', '2159', '2147', '2146', '2169', '2142', '2251']

# Paramaterizes the path of the 1 bus
path_lats = [42.373989, 42.373203, 42.375638, 42.375908, 42.375576, 42.374745, 42.372336, 42.372210, 42.371048, 42.368632, 42.360855, 42.359038, 42.343444, 42.340393, 42.333535, 42.331213, 42.332889, 42.331979, 42.330677, 42.330037]
path_lons = [-71.118910, -71.118116, -71.118449, -71.117848, -71.115702, -71.114484, -71.115128, -71.115643,-71.116074, -71.109294, -71.096016, -71.093586, -71.085840, -71.081463, -71.073351, -71.076999, -71.081076, -71.081699, -71.083244, -71.084317]

boston_lat = 42.3528
boston_lon = -71.1048
boston_x = 1092798.35753
boston_y = 2698296.888

n = len(path_lats)

def get_total_distance(xs,ys):
    d = 0
    for i in range(len(xs)-1):
        x1,x2 = xs[i],xs[i+1]
        y1,y2 = ys[i],ys[i+1]
        d += np.linalg.norm((x2-x1,y2-y1))
    return d

def plot_map(lats,lons):
    gmap = gmplot.GoogleMapPlotter(boston_lat, boston_lon, 14)
    gmap.scatter(lats, lons, '#3B0B39', size=40, marker=False)
    gmap.draw("mymap.html")

# Convert to a reasonable x,y paramaterization
def gps_to_xy(lats,lons):
    # radius of earth, pretty rough though
    R = 6371
    xs = [-R*lon*math.cos(path_lats[0]*180/math.pi)-boston_y for lon in lons]
    ys = [R*lat-boston_y for lat in lats]
    return xs,ys

def get_path():
    return gps_to_xy(path_lats,path_lons)

path = get_path()
total_distance = get_total_distance(path[0],path[1])

# Takes in a point (x,y) and a set of points (xs,ys) which create a piecewise linear path
# Then projects the point onto the closest linear section of that path
def project(x,y,xs,ys):
    smallest_d = "Taylor"
    point = None
    cum_distance = 0
    percentage = 0
    best_proj = 0
    for i in range(len(xs)-1):
        x1,x2 = xs[i],xs[i+1]
        y1,y2 = ys[i],ys[i+1]
        c,p = closest_point((x1,y1),(x2,y2),(x,y))
        d = np.linalg.norm(np.subtract(c,(x,y)))
        if d < smallest_d:
            smallest_d = d
            best_proj = p
            if p< 0 :
                p = 0
            percentage = (cum_distance + p) / total_distance
            point = c
        cum_distance += np.linalg.norm((x2-x1,y2-y1))
    return point,percentage

# Returns the closest point as well as the distance along the path
def closest_point(a, b, p):
    a_to_p = np.subtract(p,a)
    a_to_b = np.subtract(b,a)
    proj = np.dot(a_to_p,a_to_b)/np.linalg.norm(a_to_b)
    return np.add(a,proj*a_to_b/np.linalg.norm(a_to_b)), proj

def get_trajectory(filename,bus):
    route = 1
    # bus = bus_ids[11]
    direction = '1_1_var0'
    h5file = tables.open_file(filename)
    VehicleLocations = h5file.root.VehicleLocations
    queryString = "((route == '%s') & (direction == '%s'))" % (route, direction)
    trajectories = VehicleLocations.where(queryString)
    queryResults = [(timePoint['time'], timePoint['vehicleID'], timePoint['latitude'], timePoint['longitude']) for timePoint in trajectories]
    queryResults = sorted(queryResults,key=lambda x:x[0])
    filtered= queryResults
    filtered = filter(lambda x: x[1] == bus, queryResults)
    lats = [x[2] for x in filtered]
    lons = [x[3] for x in filtered]
    xs,ys = gps_to_xy(lats,lons)
    # m = 0
    # if(len(filtered)>0):
        # m = min([x[0] for x in filtered])
    ts = [x[0] for x in filtered]
    return xs,ys,ts

def get_cuts(xs,ys,ts):
    cuts = [0]
    time_threshold = 120
    distance_threshold = 1000
    for i in range(len(xs)-1):
        x1,x2 = xs[i],xs[i+1]
        y1,y2 = ys[i],ys[i+1]
        t1,t2 = ts[i],ts[i+1]
        if t2-t1 > time_threshold:
            cuts.append(i+1)
        elif math.sqrt((x2-x1)**2 + (y2-y1)**2) > distance_threshold:
            cuts.append(i+1)
    cuts.append(len(xs))
    return cuts

def sanitize(times,percentages):
    out = [(percentages[0],times[0])]
    for i in range(len(times)-1):
        p1 = percentages[i]
        p2 = percentages[i+1]
        t1 = times[i]
        t2 = times[i+1]
        if (t2-out[-1][1]) <= 0:
            continue
        speed = total_distance*(p2-out[-1][0])/(t2-out[-1][1])
        if 0 <= speed < 0.7:
            out.append((p2,t2))
    percentages_out = [x[0] for x in out]
    times_out = [x[1] for x in out]
    return percentages_out,times_out

def get_stops():
    # Represents stops with location
    bus_stop_data, directions = scrapetimetable.ReadRouteConfig(route = 1)
    the_direction = "Inbound" # Or "Outbound"
    tags = []
    for direction in directions:
        if direction[0]["name"] == the_direction:
            tags = set([x["tag"] for x in direction[1:]])
    bus_stop_data = filter(lambda x: x["tag"] in tags,bus_stop_data)
    lats = [float(x["lat"]) for x in bus_stop_data]
    lons = [float(x["lon"]) for x in bus_stop_data]
    xs,ys = gps_to_xy(lats,lons)
    pxs,pys = gps_to_xy(path_lats,path_lons)
    l = map(lambda p: project(p[0],p[1],pxs,pys), zip(xs,ys))
    stops = [x[0] for x in l]
    percentages = [x[1] for x in l]
    return stops, percentages

_, stop_percentages = get_stops()
def get_arrival_times(times,percentages):
    current_stop = 0
    out = []
    i = 0
    delta = 0.02
    for stop,stop_percentage in enumerate(stop_percentages):
        while i < len(percentages)-2 and percentages[i+1] < stop_percentage - delta:
            i += 1
        p1 = percentages[i]
        p2 = percentages[i+1]
        t1 = times[i]
        t2 = times[i+1]
        stop_str = "stop_" + str(stop)
        if p1 - delta < stop_percentage < p1 + delta:
            time = t1
            out.append({stop_str:time})
        elif p2 - delta < stop_percentage < p2 + delta:
            time = t2
            out.append({stop_str:time})
        elif p1 <= stop_percentage <= p2:
            # Just a little interpolation
            time = t1 + (t2-t1)*(stop_percentage-p1)/(p2-p1)
            out.append({stop_str:time})
    return out

plot = False
stops,stop_percentages = get_stops()

def get_features(file):
    out = []
    for bus in bus_ids:
        xs,ys,ts = get_trajectory(file,bus)
        cuts = get_cuts(xs,ys,ts)
        path_x,path_y = get_path()
        for i in range(len(cuts)-1):
            cut_start = cuts[i]
            cut_end = cuts[i+1]
            l = cut_end - cut_start
            if l < 100:
                continue
            xss = xs[cut_start:cut_end]
            yss = ys[cut_start:cut_end]
            tss = ts[cut_start:cut_end]
            mt = min(tss)
            tss = [x-mt for x in tss]
            projection = [project(x,y,path_x,path_y) for (x,y) in zip(xss,yss)]
            percentages = [p[1] for p in projection]
            percentages, tss = sanitize(tss,percentages)
            arrival_times = get_arrival_times(tss,percentages)
            if plot:
                if plot_route:
                    pylab.plot(xss,yss,'bo-',label='trajectory')
                else:
                    max_t = max(tss)
                    pylab.plot(tss,percentages,'bo-',label='data')
                    for p in stop_percentages:
                        pylab.plot((0, max_t), (p,p), 'r-')
                pylab.legend()
                pylab.axis('equal')
                pylab.show()
            date = datetime.datetime.fromtimestamp(mt).date()
            time = datetime.datetime.fromtimestamp(mt).time()
            schedule_code = scrapetimetable.TimeToScheduleCode(date)
            day_of_week = date.weekday()
            hour = time.hour
            out.append(arrival_times+[{"bus_id":bus},{"schedule_code":schedule_code},{"day_of_week":day_of_week}, {"hour":hour}])
    return out

