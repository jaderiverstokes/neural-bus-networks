#!/usr/bin/env python
import datetime
import numpy
import tables

def dist(origin, destination, radius = 6371.392896):
    # Haversine formula - takes spherical latitude and longitude in degrees and returns distance between the points
    # The default unit returned is in kilometers assuming the sphere has the radius of the earth
    lat1, lon1 = origin
    lat2, lon2 = destination

    dlat = numpy.radians(lat2-lat1)
    dlon = numpy.radians(lon2-lon1)
    a = numpy.sin(dlat/2) * numpy.sin(dlat/2) + numpy.cos(numpy.radians(lat1)) \
                                * numpy.cos(numpy.radians(lat2)) * numpy.sin(dlon/2) * numpy.sin(dlon/2)
    c = 2 * numpy.arctan2(numpy.sqrt(a), numpy.sqrt(1-a))
    d = radius * c
    return d


def GetAllIntervalData(VehicleLocations, route=1, direction='1_1_var0', position=(42.3589399, -71.09363)):
    #Defaults
    #Get data from
#   http://webservices.nextbus.com/service/publicXMLFeed?command=routeConfig&a=mbta&r=64
    # 1 bus, inbound, at 84 Mass Ave

    # 1 bus, outbound, at 84 Mass Ave
    #direction='1_0_var0'

    # CT1 bus, outbound, at 84 Mass Ave
    #route=701
    #direction='701_0_var0'

    # CT1 bus, inbound, at 84 Mass Ave
    route=701
    direction='701_1_var0'

    # 64
    #route=64
    #direction='64_0_var0'
    #position=(42.3539299, -71.13637)

    # 57 bus inbound at Comm Ave @ Hinsdale
    #route=57
    #direction='57_1_var1'
    #direction='57_1_var1'
    #position=(42.3494, -71.1030599)

    queryString = "((route == '%s') & (direction == '%s'))" % (route, direction)

    #queryString = "((route == '57') & ((direction == '57_1_var1') | (direction == '57_1_var0')))" #Outbound 57 has two variants

    trajectories = VehicleLocations.where(queryString)
    return ExtractArrivalIntervals(trajectories, position)

def ExtractArrivalIntervals(trajectories, position, doWrite = True):
    arrivalDistanceThreshold = 0.5 #km
    arrivalTimeThreshold = 300     #seconds
    maxIntervalThreshold = 2*60*60 #seconds

    queryResults = [(timePoint['time'], timePoint['vehicleID'], timePoint['latitude'], timePoint['longitude']) for timePoint in trajectories]
    queryResults = sorted(queryResults) #Sort in time

    # Try to determine when each bus arrived at the bus stop
    # TODO this is very primitive, should replace it with some kind of interpolation and least-squares approach
    data = {}
    for timePoint in queryResults:
        theDistance = dist((timePoint[2], timePoint[3]), position)
        if theDistance > arrivalDistanceThreshold:
            #Vehicle too far away, skip
            continue

        theVehicle, theTime = timePoint[1], timePoint[0]
        if theVehicle in data: #If same vehicle...
            lastTime, lastDistance = data[theVehicle][-1]
            if abs(lastTime - theTime) < arrivalTimeThreshold: #and data is recent in time
                if theDistance < lastDistance:
                    #Update - bus moved closer
                    data[theVehicle].pop()
                    data[theVehicle].append((theTime, theDistance))
            else:
                data[theVehicle].append((theTime, theDistance))
        else:
            data[theVehicle] = [(theTime, theDistance)]

    #Extract arrival times
    arrivalTimesUnsorted = []
    for vehicleData in data.values():
        for times, _ in vehicleData:
            arrivalTimesUnsorted.append(times)

    arrivalTimes = sorted(arrivalTimesUnsorted)

    arrivalIntervals = numpy.diff(arrivalTimes)
    times = numpy.array(arrivalTimes[1:]) #Associate interval with later time

    #Filter out intervals that exceed maximum gap
    times = times[arrivalIntervals < maxIntervalThreshold]
    arrivalIntervals = arrivalIntervals[arrivalIntervals < maxIntervalThreshold]
    arrivalIntervals /= 60.0     #Convert to minutes

    return arrivalIntervals, times

if __name__ == '__main__':
    from glob import glob
    all_spacings = []
    all_times = []
    for filename in sorted(glob('*.h5')):
        h5file = tables.open_file(filename)
        print 'Reading data from', filename
        spacings, times = GetAllIntervalData(h5file.root.VehicleLocations)
        h5file.close()
        all_spacings += list(spacings)
        all_times += list(times)
    if True:#doWrite:
            print len(all_times), "arrivals recorded"
            print len(all_spacings), "intervals recorded"
            import scipy.io
            data_dict = {'gaps': all_spacings, 'timestamps': all_times}
            print("data_dict",data_dict)
            scipy.io.savemat('data.mat', data_dict, oned_as = 'row')
            print 'data.mat saved'

    h5file.close()
