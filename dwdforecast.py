#
#  Copyright (C) 2020  Kilian Knoll kilian.knoll@gmx.de
#  
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
# Purpose 
#Extract weather forecast data from DWD Mosmix for a given Station ID
# 
#
#
# Background information:
# DWD provides 10 day forecast weather - and radiation data at an hourly resolution for over 5000 Stations worldwide (focus is on Germany/Europe though...)
# Description of kml file:
#https://www.dwd.de/DE/leistungen/opendata/help/schluessel_datenformate/kml/mosmix_elemente_pdf.pdf?__blob=publicationFile&v=3
#
#List of available stations:
#https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/mosmix_stationskatalog.cfg?view=nasPublication&nn=495490
#
# How to use this ?
# 1) Find the station close by your geographic location:
#   Go to the website below, zoom to your location - and click on "Mosmix Stationen anzeigen" 
#   Once you found the closest station, please change the station number to  the station number 
#   https://wettwarn.de/mosmix/mosmix.html
#   In my case, I picked Station P755 (which is close to Munich)
# 2) Make changes in code below to reflect your station number - and the corresponding URL
#   change
#       self.mystation = P755
#   below to the one you identified during step 1
#   change the URL further down below to reflect the station:
# self.urlpath = 'https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/P755/kml' 
# Your one time setup is done...
# 
# Implementation
# DWD provides two types of kml files
# single station kml files. These get updated approx every 6 hours
# all stations. These get updated hourly. However the file is pretty large. On embedded systems such as raspberry pi, I ran out of memory trying to parse XML files that size (exceeded 1GB of memory). Hence the decision to use the single station files
# The maiin routine creates a subthread. That subthread  constantly polls the DWD webserver and checks for updates. If an update is found, the file gets downloaded, unzipped and the kml file (which is sort of an XML file gets parsed)
# we are only looking for a couple of key parameters that are relevant 
#Currently the following Parameters get extracted from the kml file and put into a twodimensional array:
#mytimestamp : Timestamp of the forecast  data
#Rad1h       : Radiation Energy [kj/m²]
#TTT         : Temperature 2 m above surface [°C]
#PPPP        : Presssure Values (Surface Pressure reduced)
#FF          : Wind speed [m/s]
# 
# 
# Update July 30 2020
# Added Option to perform 'Simple' or 'Complex' mode of operation:
#Simple : Try to get weather data once only - then terminate
#Complex : Start a seperate queue that continuously polls the DWD server on the internet to get updated data 


import urllib.request
import shutil
import zipfile
from bs4 import BeautifulSoup
import requests
import xml.etree.ElementTree as ET
import time
import datetime
import queue
import threading
import logging
import pprint


pp = pprint.PrettyPrinter(indent=4)

def connvertINTtimestamptoDWD(inputstring):
    # Purpose: Convert a timestamp as presented by the UTC: 1545030000.0
    # and return it to a UTC representation: 2018-12-17T08:00:00.000000Z
    #mynewtime =time.mktime(datetime.datetime.strptime(inputstring, "%Y-%m-%dT%H:%M:%S.%fZ").timetuple())
    #print ("neue Zeit ", mynewtime)
    mysecondtime = (datetime.datetime.fromtimestamp(inputstring).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]) + "Z"     
    return (mysecondtime)  

# Main class that holds the required information 
class dwdforecast(threading.Thread):
    def __init__ (self, myqueue):
        print ("Starting dwdforecast init ...")
        self.myqueue = myqueue
        self.event = threading.Event()
        self.ext = 'kmz'
        self.mystation= 'P755'
        # Only use the "all_stations" if you got decent hardware
        #self.urlpath = 'http://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_S/all_stations/kml'
        #On Raspberries & alikes, use the one for your specific station: 
        self.urlpath = 'https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/P755/kml'
        self.lasttimecheck = 1534800680.0                   # Dec 14th 2018 (pure initialization)
        self.sleeptime = 15                                 #Time interval we poll the server [seconds]- please increase time since updates from DWD are hourly at best
        self.myinit = 0                                                                                     #So we can populate the queue initially / subsequently
        threading.Thread.__init__ (self)
        print ("I am looking for data from DWD for the following station: ", self.mystation)
        print ("I will be polling the following URL for the latest updates ", self.urlpath)

    # Based on the user specified URL, find the latest file file with it´s timestamp 
    def GetURLForLatest(self,urlpath, ext=''):
        try:
            page = requests.get(urlpath).text
        except Exception as ErrorGetWebdata:
            logging.error("%s %s",",GetURLForLatest Error getting data from the internet:", ErrorGetWebdata)
        soup = BeautifulSoup(page, 'html.parser')
        soup_reduced= soup.find_all('pre')
        soup_reduced = soup_reduced[0]
        counter = 0
        for elements in soup_reduced:
            elements = str(elements)
            if (counter >0):
                words =elements.split()
                mytime = words[0] +"-" + words[1]
                logging.debug("%s %s" ,",GetURLForLatest :DWD Filetimestamp found :", mytime)
                mynewtime =time.mktime(datetime.datetime.strptime(mytime, "%d-%b-%Y-%H:%M").timetuple())
                logging.debug("%s %s" ,",GetURLForLatest :DWD Filetimestamp found :", mynewtime)
                #print ("From function GetURLForLatest -mynewtime", 2*mynewtime)
            
            if (elements.find("LATEST") >0):
                #print ("My element", elements)
                counter = 1
        myurl = [urlpath + '/' + node.get('href') for node in soup.find_all('a') if node.get('href').endswith(ext)]
        return (myurl, mynewtime)

        
    def connvertDWDtimestamptoINT(self,inputstring):
        # Purpose: Convert a timestamp as presented by the DWD: 2018-12-25T07:00:00.000Z
        # and return it to a UTC representation
        mynewtime =time.mktime(datetime.datetime.strptime(inputstring, "%Y-%m-%dT%H:%M:%S.%fZ").timetuple())
        #print ("neue Zeit ", mynewtime)
        #mysecondtime = datetime.datetime.fromtimestamp(mynewtime).strftime('%Y-%m-%dT%H:%M:%S.%fZ')     
        #print ("Einmal retour", mysecondtime)
        mycurrentINTtimestamp =int(mynewtime)
        return (mycurrentINTtimestamp)
   
    
    def connvertDWDtimestamptoINT(self,inputstring):
        # Purpose: Convert a timestamp as presented by the DWD: 2018-12-25T07:00:00.000Z
        # and return it to a UTC representation
        mynewtime =time.mktime(datetime.datetime.strptime(inputstring, "%Y-%m-%dT%H:%M:%S.%fZ").timetuple())
        mycurrentINTtimestamp =int(mynewtime)
        return (mycurrentINTtimestamp)
        
      
                
            
    try:
        def run(self):
            while not self.event.is_set():            #In case the main process wants to shut us down...
                if (self.myinit== 0):                 #We populate the first timestamp to signal to main that we are up & running
                    temptimestamp = time.time()
                    print ("From dwdforecast - initial queue population", temptimestamp)
                    self.myqueue.put(temptimestamp)
                    self.myinit = 1
                time.sleep(1)
                try:
                    self.mydownloadfiles, self.mynewtime = self.GetURLForLatest(self.urlpath, self.ext)
                    #print ("Downloadfiles = ", self.mydownloadfiles)
                    #print ("Timestamp    = ", self.mynewtime)
                except Exception as ErrorReadFromDWD:
                    logging.error("%s %s" ,",dwdforecast  :", ErrorReadFromDWD)
            
                self.myarray =[]
                for self.file in self.mydownloadfiles:
                    self.myarray.append(self.file)
                self.temp_length = len(self.myarray)
                self.url = self.myarray[self.temp_length-1]

                logging.debug("%s %s %s",",dwdforecast : -BEFORE  if- time comparison :", self.mynewtime, self.lasttimecheck)                
                if (self.mynewtime > self.lasttimecheck):
                    logging.debug("%s %s %s" ,",dwdforecast : -in if- time comparison :", self.mynewtime, self.lasttimecheck)
                    #print ("DWD Weather - we have found a new kml file that we will download - timestamp was :", self.mynewtime)
                    #print ("DWD Weather -  self.lasttimecheck was ", self.lasttimecheck)
                    self.lasttimecheck = self.mynewtime
                    self.file_name = "temp1.gz"
                    self.out_file = "temp2.gz"
                    self.targetdir ="./"
                    try:
                        time.sleep(10)                                          #Assumption is - we see the file on the DWD server - but it has not yet been copied over
                        # Download the file from `url` and save it locally under `self.file_name`:
                        with urllib.request.urlopen(self.url) as self.response, open(self.file_name, 'wb') as self.out_file:
                            shutil.copyfileobj(self.response, self.out_file)
                        time.sleep(5)                                           #not sure if this gets rid of the access problems                  
                        with zipfile.ZipFile(self.file_name,"r") as zip_ref:
                            Myzipfilename = (zip_ref.namelist())
                            Myzipfilename = str(Myzipfilename[0])
                            zip_ref.extractall(self.targetdir)    
                        logging.debug("%s %s" ,",dwdforecast : -File that I extract is zipfile :", Myzipfilename)
                        time.sleep(5)                                           #not sure if this gets rid of the access problems
                    except Exception as MyException:
                        logging.error("%s %s", ",subroutine dwdforecast exception getting the data from server : ", MyException)    
                        
                    self.tree = ET.parse(Myzipfilename) 
                    self.root = self.tree.getroot()
                    self.root.tag     
                    """      
                        <kml:kml xmlns:dwd="https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:xal="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
                        
                        <kml:kml xmlns:dwd="https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:xal="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
                    """
                    #--------------------------------------------------
                    #Namespace definition for kml file:
                    #
                    self.ns = {'dwd': 'https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd', 'gx': 'http://www.google.com/kml/ext/2.2',
                    'kml': 'http://www.opengis.net/kml/2.2', 'atom': 'http://www.w3.org/2005/Atom', 'xal':'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0'}
                    #--------------------------------------------------
                    # We get the timestamps
                    #
                    self.timestamps = self.root.findall('kml:Document/kml:ExtendedData/dwd:ProductDefinition/dwd:ForecastTimeSteps/dwd:TimeStep',self.ns)
                    self.i = 0
                    self.timevalue=[]
                    for self.child in self.timestamps:
                        #print ("TIMESTAMPS",  child.text)
                        self.timevalue.append(self.child.text)
                    """
                    for j in timevalue:
                        print ("Zeit",i, " ", timevalue[i])
                        i = i+1
                    """
                        
                    for self.elem in self.tree.findall('./kml:Document/kml:Placemark',self.ns):                    #Position us at the Placemark
                        #print ("SUCERJH ", sucher)
                        #print ("Elemente ", elem.tag, elem.attrib, elem.text)
                        self.mylocation = self.elem.find('kml:name',self.ns).text                                  #Look for the station Number
                        
                        # Hier IF Frage einbauen
                        if (self.mylocation == self.mystation):   
                            #print ("meine location", self.mylocation)
                            self.myforecastdata = self.elem.find('kml:ExtendedData',self.ns)
                            for self.elem in self.myforecastdata:                                         
                                #We may get the following strings and are only interested in the right hand quoted property name WPcd1:
                                #{'{https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd}elementName': 'WPcd1'}
                                self.trash = str(self.elem.attrib)
                                self.trash1,self.mosmix_element = self.trash.split("': '")
                                self.mosmix_element, self.trash = self.mosmix_element.split("'}")
                                #-------------------------------------------------------------
                                # Currently looking at the following key Data:
                                # Looking for the following mosmix_elements 
                                #FF : Wind Speed            [m/s]
                                #Rad1h : Global irridance   [kJ/m²]
                                #TTT : Temperature 2m above ground [Kelvin]
                                #PPPP : Pressure reduced    [Pa]
                                #-------------------------------------------------------------
                                if ('FF' == self.mosmix_element):
                                    self.FF_temp = self.elem[0].text
                                    self.FF = list (self.FF_temp.split())
                                if ('Rad1h' == self.mosmix_element):
                                    self.Rad1h_temp = self.elem[0].text
                                    self.Rad1h = list (self.Rad1h_temp.split())
                                if ('TTT' == self.mosmix_element):
                                    self.TTT_temp = self.elem[0].text
                                    self.TTT = list(self.TTT_temp.split())
                                    counter = 0 
                                    # We convert from Kelvin to Celcius...:
                                    for i in self.TTT:
                                        self.TTT[counter]=round((float(self.TTT[counter])-273.13),2)
                                        #print (self.TTT[counter])
                                        counter = counter +1
                                if ('PPPP' == self.mosmix_element):
                                    self.PPPP_temp = self.elem[0].text
                                    self.PPPP = list (self.PPPP_temp.split())
                    
                    
                    #------------------------------------
                    # Define empty array                
                    self.mosmixdata =[]
                    for self.j in range(6):                                      #Right now we have timevalue, mytimestamp, self.FF Rad1h TTT PPPP
                        self.column = []
                        self.counter = 0
                        for self.i in self.timevalue:
                            self.column.append(0)
                        self.mosmixdata.append(self.column)
                    #------------------------------------
                    #Populate values
                    counter = 0
                    
                    for self.i in self.timevalue:
                        self.mytimestamp = self.connvertDWDtimestamptoINT(self.timevalue[counter])
                        self.mosmixdata[0][counter]=self.timevalue[counter]
                        self.mosmixdata[1][counter]=self.mytimestamp
                        self.mosmixdata[2][counter]=self.Rad1h[counter]
                        self.mosmixdata[3][counter]=self.TTT[counter]
                        self.mosmixdata[4][counter]=self.PPPP[counter]
                        self.mosmixdata[5][counter]=self.FF[counter]
                        counter = counter + 1
                    #------------------------------------------

                    self.cols = len(self.mosmixdata)
                    rows = 0
                    if self.cols:
                        self.rows = len(self.mosmixdata[0])
                    self.MosmixFileFirsttimestamp = self.mosmixdata[1][0]
                    #print ("My first stamp from the file is:",self.mosmixdata[0][0],"Endstring",self.mosmixdata[1][0] )       
                    #print ("-------------------------------------------------")
                    #print (self.mosmixdata)
                    self.indexcounter_addrows=1
                    self.MyWeathervalues = {}
                    try:
                        print ("Here is what we got from DWD :")
                        for j in range(self.rows):
                            if (self.indexcounter_addrows >0):                                       #We are adding from the point onward - see self.indexcounter_addrows if check below
                                #print ("counting indices", self.indexcounter_addrows)
                                self.MyWeathervalues.update({'mydatetime':self.mosmixdata[0][j]})
                                self.MyWeathervalues.update({'mytimestamp':self.mosmixdata[1][j]})
                                self.MyWeathervalues.update({'Rad1h':self.mosmixdata[2][j]})
                                self.MyWeathervalues.update({'TTT':self.mosmixdata[3][j]})
                                self.MyWeathervalues.update({'PPPP':self.mosmixdata[4][j]})
                                self.MyWeathervalues.update({'FF':self.mosmixdata[5][j]})  
                               
                                print ('mydatetime',self.mosmixdata[0][j],'mytimestamp ',self.mosmixdata[1][j],'Rad1h ',self.mosmixdata[2][j],'TTT ',self.mosmixdata[3][j], 'PPPP',self.mosmixdata[4][j],'FF',self.mosmixdata[5][j])

                        
                        self.mytimestamp = connvertINTtimestamptoDWD(self.mynewtime)
                        logging.debug ("%s %s %s %s", ",Subroutine dwdforecast -we have used DWD file from time : ", self.mynewtime, " ", self.mytimestamp)
                    except Exception as ErrorDWDArray:
                        print ("Shit happened  ?", ErrorDWDArray)
                        logging.error ("%s %s", ",subroutine dwdforecast final exception : ", ErrorDWDArray)
                    logging.debug("%s %s", "From dwdforecast - we have found a true commit and have updated the database at the following dwd time :", self.mynewtime)
                    time.sleep(self.sleeptime)          # We are putting in a sleep 
                    self.myqueue.put(self.mynewtime)
                else:
                    pass
                    print("No new data.....")
                time.sleep(self.sleeptime)              # We are pausing to not constantly cause internet traffic
            print ("Thread is going down ...")
    except Exception as ExceptionError:
            print ("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
            print ("XXX-Aus Subroutine dwdforecast -verrant ? ", ExceptionError)
            print ("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
            logging.error("%s %s", ",subroutine dwdforecast final exception : ", ExceptionError)

                    

if __name__ == "__main__":

    logging.basicConfig(filename="dwd_debug.txt",level=logging.DEBUG)
    #
    """
    Interaction can be 'Simple' - or 'Complex'
    Simple : Try to get weather data once only - then terminate
    Complex : Start a seperate queue that continuously polls the DWD server on the internet to get updated data 
    """
    Interaction = 'Simple' #Interaction can be 'Simple' - or 'Complex'
    #

    
    
    #-----------------------------------------------------------------
    # START Queue (To read dwd values and populate them to database):
    try:
        myQueue1 = queue.Queue()                                               
        myThread1= dwdforecast(myQueue1)                          
        myThread1.start()                                                             
        while myQueue1.empty():                                                  
            print(" Waiting on DWD dwdforecastdata Queue results to tell it is started...")
            logging.info("%s " ",Main :Waiting on Queue results to be populated ...")
            time.sleep(1)
        # Queue End (To read values from DWD)
        #_________________________________________________________________
        i = 0 
            
        try:
            while i <1: 
                if not myQueue1.empty():                                      # Falls was in der Queue steht machen wir was
                    quelength = myQueue1.qsize()                               # Wenn da viele Werte angelaufen sind, nehmen wir jetzt einfach den Letzten
                    #print ("LAENGE der QUEUE -XXXXXXXXXXXXXXXXXXXXXXX : ", quelength) 
                    logging.info("%s %s " ,",Main :Queue length is : ", quelength) 
                    
                    for x in range (0,quelength):
                        LastDWDtimestamp = myQueue1.get()                     # Das ist die magische Zeile in der wir den Wert aus der Queue abholen 
                        mylasttimestamp = connvertINTtimestamptoDWD(LastDWDtimestamp)
                    print ("From Main : DWD File access I checked /  got uploaded by DWD was at :", LastDWDtimestamp,mylasttimestamp )
                if (Interaction == 'Simple'):   
                    print ("Interaction is Simple - processing once only")
                    i = i +1
                else:
                    pass
                time.sleep(1)
            time.sleep(60)
            myThread1.event.set()
            print ("Closing thread & exiting")
        except KeyboardInterrupt:
            #Abfangen, wenn der Anwender Ctrl-C drueckt 
            print (" Sub - User is trying to kill me ...  \n") 
            myThread1.event.set()
            print ("Thread from Sub ... stopped")
        except Exception as OtherExceptionError:  
            print ("hit some other error....    !", OtherExceptionError)
            myThread1.event.set()
            
                
    except KeyboardInterrupt:
        #Abfangen, wenn der Anwender Ctrl-C drueckt 
        print ("User hit Ctrl-C - and tries to kill me ...- starting to signal thread termination \n") 
        myThread1.event.set()
    except Exception as FinalExceptionError:  
        print ("I am clueless ... Hit some other error ....    !", FinalExceptionError)
        myThread1.event.set()
        
 
 


