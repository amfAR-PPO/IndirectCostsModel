#!/usr/bin/env python
# coding=UTF-8

#Required Python Libraries
import MySQLdb
import sys
import csv
from random import random
from decimal import Decimal
from prettytable import PrettyTable
import setupserver

# Set baseline assumptions. 
Assumptions={
	'Years': [2007,2008,2009,2010,2011,2012,2013,2014,2015,2016],
	'Totals': ['Total Funding', 'NEC'],
	'Scenarios': ['Scenario A', 'Scenario B', 'Scenario C', 'Assumed 20%', 'Assumed 15%', 'Assumed 10%'],
	'Exclusions': ['Sub-Awards', 'Capital Expenditures', 'Motor Vehicles', 'Lab Equipment', 'ARV Drugs'],
	'EquipAssumption': Decimal(0.4),

	# '%' will run for all countries in grouped analysis. Change to "Individual" to for each country individually, or for a single country, enter the name.
	'Country': ['%'],

	# The following assumptions can be used to randomly assign a percentage of organizations receiving less than the NonNICRACap in PEPFAR funding from a single agency to only receive the NonNICRARate indirect cost recovery. NonNICRARate is set at the de minimus 10% rate available to all partners. NonNICRAIOs Range between 0.0 and 1.
	'NonNICRAIOs': 0.0,
	'NonNICRACap': 10000000,
	'NonNICRARate': 0.1,
}

if len(sys.argv)>1:
	Assumptions['Country']=[sys.argv[1]]

# Modifiers to proportionally adjust exclusion amounts - used as multipliers so 1 has no effect. Not used in the calculations for the paper, but useful to evaluate the relative of exclusions
Modifiers={
	'Sub-Awards': Decimal(1),
	'Capital Expenditures': Decimal(1),
	'Motor Vehicles': Decimal(1),
	'LabEquipment': Decimal(1),
	'arvs': Decimal(1),
}

# Create the DB connection - connection information example in setupserver - example.py - copy to setupserver.py and replace DB credential information
db = MySQLdb.connect(setupserver.host,setupserver.user,setupserver.passwd,setupserver.db) # (<server>, <username>, <password>, <databasename>)
cursor = db.cursor(MySQLdb.cursors.DictCursor)

# Create global variables

# Exclusions
SubPartnerRates=False
CalculateCapitalExpenditures=False
MotorVehicles=False
LabEquipment=False
ARVs=False

# Orgtypes
OrgTypes=False
OrgTypeRatios=False

# NICRAs
NICRAs=False

# Trackers
Scenarios = {}
Exclusions = {}
Totals = {}
cs = []
Years = []
CountryTable=''
NAAllocationTotals={'IO': 0, 'Universities': 0}
NA=0

def main():
	global cs
	global Years
	global CountryTable
	global Modifiers
	global SensitivityAnalysisRuns
	global NAAllocationTotals
	
	# Get countries from database if necessary
	cs = getcountries();
	
	# Setup years for tables purposes
	Years = getyearsfortables();
	
	# Setup table output for Individual Country Results Table - Only meaningful if "Individual" is selected for country runs
	CountryTable=PrettyTable(['',str(Years[-2]),' ','Total (' + str(min(Years)) + '-'+ str(Years[-2]) + ')','  '])
	CountryTable.align = 'r'
	CountryTable.align['']='l'
	CountryTable.add_row(['','A (On-Campus)','Assumed 10%','A (On-Campus)','Assumed 10%'])
	
	for country in cs:
		if country=='%':
			print "All Countries"
		elif country=="Cote d'Ivoire": # apostrophe can cause issues in the mysql query.
			print country
			country="Cote d%"
		else:
			print country
		
		NAAllocationTotals={'IO': 0, 'Universities': 0}
		
		# Reports the Allocation totals being tracked
		totalallocations(country);
		mainRun(country);
		
		print('**********NA Allocations**********')
		print('IOs: ' + str('{:,}'.format(round(NAAllocationTotals['IO'],0))).replace('.0','') + ' (' + str(round(NAAllocationTotals['IO']/NATotal,4)*100) + '%)')
		print('Universities: ' + str('{:,}'.format(round(NAAllocationTotals['Universities'],0))).replace('.0','') + ' (' + str(round(NAAllocationTotals['Universities']/NATotal,4)*100) + '%)')
		print('********END NA Allocations********')
		print 'Country Tables'
	print CountryTable

# Fetch country list from Database if 'Individual' selected in assumptions.
def getcountries():
	cs=[]
	
	if Assumptions['Country'][0]=='Individual':
		cursor.execute("SELECT DISTINCT COPCC from COPs where 1 order by COPCC")
		countries=cursor.fetchall()
		for c in countries:
			cs.append(c['COPCC'])
	else:
		cs=Assumptions['Country']
	return cs

# Output topline information relevant to overall model such as total COP funding, funding per Partner location, and total numbers of partners
def totalallocations(country):
	cursor.execute("SELECT SUM(CODEAMOUNT) from COPs WHERE COPCC LIKE '" + country + "' and BUDGETCODE='TOTL' and COPYY BETWEEN " + str(Assumptions['Years'][0]) + " and " + str(Assumptions['Years'][-1]))
	TotalFunding = cursor.fetchall()
	print("Total Funding: " + str('{:,}'.format(TotalFunding[0]['SUM(CODEAMOUNT)'])))
	
	cursor.execute("SELECT PARTNERLOCATION,ORGTYPE,SUM(CODEAMOUNT) from COPs WHERE COPCC LIKE '" + country + "' and BUDGETCODE='TOTL' and COPYY BETWEEN " + str(Assumptions['Years'][0]) + " and " + str(Assumptions['Years'][-1]) + " group by PARTNERLOCATION,ORGTYPE")
	LocationFunding = cursor.fetchall()
	
	NA = 0
	IO = 0
	Local=0
	UNIV = 0
	USG = 0
	for L in LocationFunding:
		if L['PARTNERLOCATION']=='International' and L['ORGTYPE']=='University':
			UNIV+=L['SUM(CODEAMOUNT)']
		elif L['PARTNERLOCATION']=='International':
			IO+=L['SUM(CODEAMOUNT)']
		elif L['PARTNERLOCATION']=='Local':
			Local+=L['SUM(CODEAMOUNT)']
		elif L['PARTNERLOCATION']=='USG':
			USG+=L['SUM(CODEAMOUNT)']
		else:
			NA+=L['SUM(CODEAMOUNT)']
	
	# Generate Output to Console
	print('*****************Topline Information***************')
	print("IO: Amount: "+str('{:,}'.format(IO)) +" ("+str(round(IO/TotalFunding[0]['SUM(CODEAMOUNT)'],4)*100)+"%)")
	print("UNIV: Amount: "+str('{:,}'.format(UNIV))+" ("+str(round(UNIV/TotalFunding[0]['SUM(CODEAMOUNT)'],4)*100)+"%)")
	print("Local: Amount: "+str('{:,}'.format(Local))+" ("+str(round(Local/TotalFunding[0]['SUM(CODEAMOUNT)'],4)*100)+"%)")
	print("USG: Amount: "+str('{:,}'.format(USG))+" ("+str(round(USG/TotalFunding[0]['SUM(CODEAMOUNT)'],4)*100)+"%)")
	print("NA: Amount: "+str('{:,}'.format(NA))+" ("+str(round(NA/TotalFunding[0]['SUM(CODEAMOUNT)'],4)*100)+"%)")
	global NATotal
	global PEPFARTotal
	PEPFARTotal = TotalFunding[0]['SUM(CODEAMOUNT)']
	NATotal = NA
	
	# Output the total number of unique Prime Partners
	cursor.execute("SELECT PARTNER from COPs WHERE COPCC LIKE '" + country + "' and COPYY BETWEEN " + str(Assumptions['Years'][0]) + " and " + str(Assumptions['Years'][-1]) + ' and CODEAMOUNT>0 group by PARTNER')
	Partners = cursor.fetchall()
	print('Total Number of Unique Partners: ' + str(len(Partners)))
	print('**************End Topline Information**************')

# Establish a copy of Assumptions['Years'] and append additional columns for use in tables and for totals tabulation
def getyearsfortables():
	Years=[]
	for Y in Assumptions['Years']:
		Years.append(Y)
	Years.insert(0,'')
	Years.append('Total')
	return Years

def mainRun(country):
	global CountryTable
	
	# Declare variable for modification
	global Scenarios
	global Exclusions
	global Totals

	# Fills in the Dictionary Structure to track the Scenario and Exclusions Calculations
	for S in Assumptions['Scenarios']:
		Scenarios[S]={}
		for year in Assumptions['Years']:
			Scenarios[S][str(year)]=0
	for E in Assumptions['Exclusions']:
		Exclusions[E]={}
		for year in Assumptions['Years']:
			Exclusions[E][str(year)]=0
	for T in Assumptions['Totals']:
		Totals[T]={}
		for year in Assumptions['Years']:
			Totals[T][str(year)]=0
	
	# Calculate SubPartner Retention Rates and Fetch Dictionary of Results
	global SubRetentionRates
	SubRetentionRates=CalculateSubpartnerRetentionRates();

	# Calculate Capital Expenditure Exclusions and Fetch Dictionary of Results
	global CapitalExpenditures
	CapitalExpenditures=CalculateCapitalExpenditures(country);

	# Calculate Motor Vehicle Exclusions and Fetch Dictionary of Results
	global MotorVehicles
	MotorVehicles=CalculateMotorVehicles(country);

	# Calculate Lab Equipment Exclusions and Fetch Dictionary of Results
	global LabEquipment
	LabEquipment=CalculateLabEquipment(Assumptions['EquipAssumption'],country);
	
	# Calculate ARV Drug Exclusions and Fetch Dictionary of Results
	global ARVs
	ARVs=CalculateARVExclusions(country);

	# Get Organizational Types for all international partners and Fetch Dictionary of Results
	global OrgTypes
	OrgTypes=GetOrgTypes();

	# Calculate the ratio of NA funds that should be allocated to different org types
	global OrgTypeRatios
	OrgTypeRatios=CalculateOrgTypeRatios(country);

	# Get NICRA rates and Fetch Dictionary of Results
	global NICRAs
	NICRAs=GetNICRAs();
	
	# Run the Partner Model - Used to calculate indirects for allocations to identifiable implementing partners
	PartnerModel(country);
	
	# Run the NA (Not Available) Model - Used to calculate indirects for money not allocated to identifiable implementing partners
	NAModel(country);
	
	# Setup table output for each year. [Table 3 in paper]
	Table=PrettyTable(Years)
	Table.align = 'r'
	Table.align['']='l'
	
	Ttotals={}
	Ytotals={}
	ModelTotal=0
	row=['Total Funding']
	for Y,A in sorted(Totals['Total Funding'].items()):
		row.append(int(round(A,0)))
		#print Y + ': ' +str(A)
		ModelTotal+=A
		
	# Start Output section and headline numbers
	print('**********Total Model Outcomes***********')
	print('Total PEPFAR Funding: ' + str('{:,}'.format(PEPFARTotal)))
	print('Total Funding Included: ' + str('{:,}'.format(int(ModelTotal))) + ' (' + str(round(float(ModelTotal)/float(PEPFARTotal)*100,2)) + '%)')
	
	row.append(int(round(ModelTotal,0)))
	Table.add_row(row)
	t=0
	row=["Total NEC Funding"]
	for Y,A in sorted(Totals['NEC'].items()):
		row.append(int(round(A,0)))
		#print Y + ': ' +str(A)
		t+=A
	print('Total NEC Funding Included: ' + str('{:,}'.format(int(t))) + ' (' + str(round(float(t)/float(ModelTotal)*100,2)) + '%)')
	row.append(int(round(t,0)))
	Table.add_row(row)
	t=0
	for S in Assumptions['Scenarios']:
		row=[S]
		for Y, A in sorted(Scenarios[S].items()):
			#print Y + ': ' +str(A)
			row.append(int(round(A,0)))
			if Y==str(max(Assumptions['Years'])):
				Ytotals[S]=A
			t+=A
		print(S + ': ' + str('{:,}'.format(int(t))) + ' (' + str(round(float(t)/float(ModelTotal)*100,2)) + '%)')
		row.append(int(round(t,0)))
		Ttotals[S]=t
		Table.add_row(row)
		t=0
	for E in Assumptions['Exclusions']:
		row=[E]
		for Y, A in sorted(Exclusions[E].items()):
			#print Y + ': ' +str(A)
			row.append(int(round(A,0)))
			t+=A
		print(E + ': ' + str('{:,}'.format(int(t))) + ' (' + str(round(float(t)/float(ModelTotal)*100,2)) + '%)')
		row.append(int(round(t,0)))
		Table.add_row(row)
		t=0
	Trange = sum(Scenarios['Scenario A'].values())-sum(Scenarios['Assumed 10%'].values())
	Yrange = Scenarios['Scenario A'][str(Assumptions['Years'][-1])]-Scenarios['Assumed 10%'][str(Assumptions['Years'][-1])]
	print('Total Extent of Range of Indirects: ' + '{:,}'.format(round(Trange,0)) + ' (' + str(round(Trange/ModelTotal*100,2)) + '%)')
	try:
		print('Extent of Range in Final Year (' + str(Assumptions['Years'][-1]) + '): ' + '{:,}'.format(round(Yrange,0)) + ' (' + str(round(Yrange/Totals['Total Funding'][str(Assumptions['Years'][-1])]*100,2)) + '%)')
	except ZeroDivisionError:
		print('Extent of Range in Final Year (' + str(Assumptions['Years'][-1]) + '): ' + '{:,}'.format(round(Yrange,0)) + ' (NA)')
	print('*******END Total Model Outcomes***********')
	print('**********Results Table*******************')
	print(Table)
	print('*********END Results Table****************')
	
	# Add data to Country Table - Excluded from paper
	CountryTable.add_row([country,int(round(Ytotals['Scenario A'])),int(round(Ytotals['Assumed 10%'])),int(round(Ttotals['Scenario A'])),int(round(Ttotals['Assumed 10%']))])
	
# Function calculates and returns a dictionary of the average retention rates for each partner and the overall averages. Structure is {'Partner': {<partnername><agency>: <rate>, ...n}, 'Agency': {<agencyname>: <rate>, ...n,}, 'Average': <rate>}
def CalculateSubpartnerRetentionRates():
	cursor.execute("SELECT SUBPARTNER,FUNDAGENCY from SubPartners WHERE COPYY=2007 and AMOUNT>0 group by SUBPARTNER,FUNDAGENCY")
	Sub2007 = cursor.fetchall()
	
	cursor.execute("SELECT PARTNER,FUNDAGENCY,SUM(AMOUNT) from SubPartners WHERE COPYY BETWEEN 2007 and 2009 and PARTNERLOCATION='International' and AMOUNT>0 group by PARTNER,FUNDAGENCY order by PARTNER,FUNDAGENCY")
	SubAmounts = cursor.fetchall()
	
	InternationalProportions={ #These are the proportions of subawards to IOs and Universities hand calculated from COP 2007 data. Data available in spreadsheet form
		'HHS/HRSA': Decimal(0.409037830690989), 
		'USAID': Decimal(0.282877198948748), 
		'HHS/CDC': Decimal(0.267480867917712), 
		'USDOD': Decimal(0.763636363636364),
	}
	
	#InternationalProportions={ #Uncomment this dictionary to remove proportional allocation of sub-awards to IOs and Universities
		#'HHS/HRSA': Decimal(0), 
		#'USAID': Decimal(0), 
		#'HHS/CDC': Decimal(0), 
		#'USDOD': Decimal(0),
	#}

	# Gather partner totals - note that BUDGETCODE='TOTL' must be included or results will be doubled. 
	cursor.execute("SELECT PARTNER,FUNDAGENCY,SUM(CODEAMOUNT) from COPs WHERE COPYY BETWEEN 2007 and 2009 and PARTNERLOCATION='International' and BUDGETCODE='TOTL' group by PARTNER,FUNDAGENCY order by PARTNER,FUNDAGENCY")
	Tdata = cursor.fetchall()
	Ptotals={}
	for row in Tdata:
		Ptotals[row['PARTNER']+row['FUNDAGENCY']]=row['SUM(CODEAMOUNT)']
	Pretentionrates={} #Holds <Partner><Agency> retention rates
	Prawret=[] #Holds raw retention rates for calculating uncompensated averate
	Aamounts={} #Holds partner totals
	Asubamounts={} #Holds subpartner totals
	PartnersWithSubs=0
	for row in SubAmounts:
		if Ptotals[row['PARTNER']+row['FUNDAGENCY']]>0:
			rate=1-(row['SUM(AMOUNT)']/Ptotals[row['PARTNER']+row['FUNDAGENCY']]) #Calculates the retention rate (1-subpartnerAwards/PartnerTotal)
			if rate < 1:
				PartnersWithSubs+=1
				Prawret.append(rate)
				try:
					Pretentionrates[row['PARTNER']+row['FUNDAGENCY']]=1-((1-rate)*(1-InternationalProportions[row['FUNDAGENCY']]))
				except KeyError:
					Pretentionrates[row['PARTNER']+row['FUNDAGENCY']]=rate
				try:
					Aamounts[row['FUNDAGENCY']].append(Ptotals[row['PARTNER']+row['FUNDAGENCY']])
					Asubamounts[row['FUNDAGENCY']].append(row['SUM(AMOUNT)'])
				except KeyError:
					Aamounts[row['FUNDAGENCY']]=[]
					Asubamounts[row['FUNDAGENCY']]=[]
					Aamounts[row['FUNDAGENCY']].append(Ptotals[row['PARTNER']+row['FUNDAGENCY']])
					Asubamounts[row['FUNDAGENCY']].append(row['SUM(AMOUNT)'])
	
	RetentionTable=PrettyTable(["Agency","","Rate"])
	RetentionTable.align = 'l'
	RetentionTable.align['Rate'] = 'r'
	Aretentionrateaverages={} #Holds the Agency Retention Averages
	Aretentionrateaverages1={} #Holds unmodified averages for table output
	
	# Calculate Agency retention averages
	for agency,amounts in Aamounts.items():
		Aretentionrateaverages[agency]=1-(sum(Asubamounts[agency])/sum(amounts))
		Aretentionrateaverages1[agency]=1-(sum(Asubamounts[agency])/sum(amounts))
	for agency, rate in InternationalProportions.items():
		Aretentionrateaverages[agency]=1-(1-Aretentionrateaverages1[agency])*(1-rate)
	for agency, rate in Aretentionrateaverages.items():
		RetentionTable.add_row([agency,"",""])
		RetentionTable.add_row(["","Average Retention Rate",str(round(Aretentionrateaverages1[agency],4)*100)+"%"])
		try:
			RetentionTable.add_row(["","Average IO Proportion",str(round(InternationalProportions[agency],4)*100)+"%"])
		except KeyError:
			RetentionTable.add_row(["","Average IO Proportion","0%"])
		RetentionTable.add_row(["","Applied Average",str(round(Aretentionrateaverages[agency],4)*100)+"%"])
	
	# Calculate an "All Others" retention rate to be applied where Agency rates are lacking
	cursor.execute("SELECT SUM(CODEAMOUNT) from COPs WHERE COPYY BETWEEN 2007 and 2009 and BUDGETCODE='TOTL' and PARTNERLOCATION='International'")
	Total = cursor.fetchall()
	cursor.execute("SELECT SUM(AMOUNT) from SubPartners WHERE COPYY BETWEEN 2007 and 2009 and PARTNERLOCATION='International'")
	Subtotal = cursor.fetchall()
		
	Average = 1-(Subtotal[0]['SUM(AMOUNT)']/Total[0]['SUM(CODEAMOUNT)'])
	RetentionTable.add_row(["All Others","",""])
	RetentionTable.add_row(["","Applied Average",str(round(Average,4)*100)+'%'])
	print RetentionTable
	
	# Below prints the number of partner->agency pairs and the number that did report subpartner data
	cursor.execute("SELECT PARTNER,FUNDAGENCY,SUM(CODEAMOUNT) from COPs WHERE COPYY BETWEEN " + str(Assumptions['Years'][0]) + " and " + str(Assumptions['Years'][-1]) + " and PARTNERLOCATION='International' and BUDGETCODE='TOTL' and CODEAMOUNT>0 group by PARTNER,FUNDAGENCY order by PARTNER,FUNDAGENCY")
	Tdata = cursor.fetchall()
	PAllYearstotals={}
	for row in Tdata:
		PAllYearstotals[row['PARTNER']+row['FUNDAGENCY']]=row['SUM(CODEAMOUNT)']
	
	AverageRet = Pretentionrates.values()
	print('**********Partner Average Retention Rate*******************')
	print('Average Applied Partner Retention Rate for Partners with Sub-awards: ' + str(round(sum(AverageRet)/len(AverageRet)*100,2)) + '%')
	print('Average Without IO Compensation: ' + str(round(sum(Prawret)/len(Prawret)*100,2)) + '%')
	print('********END Partner Average Retention Rate*****************')
	
	cov = round(float(PartnersWithSubs)/float(len(Ptotals))*100,2)
	print('********Partner->Agency Combinations with Subpartners********')
	print('Total Partner->Agency Pairs (2007-2009): ' + str(len(Ptotals)))
	print('Total Partner->Agency Pairs with Subs: ' + str(PartnersWithSubs))
	print('Coverage Percentage: ' + str(cov) + '%')
	print('Total Partner->Agency Combinations (All Years in Dataset): ' + str(len(PAllYearstotals)))
	print('Total Unique Subpartners in 2007: ' + str(len(Sub2007)))
	print('********End Partner->Agency Combinations Section*************')
	
	return {'Partner': Pretentionrates, 'Agency': Aretentionrateaverages, 'Average': Average}

# Function gathers exclusions based on capital expenditures (Construction and Renovation costs) for each partner by agency. Data for 2010-2015 available. Data for 2007-2009 utilize percentage rates. Structure returned is {'Partner': {<partnername><agency><year>: <amount>, ...n}, 'Average': <rate>}
def CalculateCapitalExpenditures(country):
	# Fetch Data
	cursor.execute("SELECT COPYY,PARTNER,FUNDAGENCY,SUM(CODEAMOUNT) from CrossCut WHERE COPCC LIKE '" + country + "' and COPYY between 2010 and " + str(Assumptions['Years'][-1]) + " and PARTNERLOCATION='International' and (CATEGORY LIKE 'Construction%' or CATEGORY='Renovation') group by COPYY,PARTNER,FUNDAGENCY order by PARTNER,FUNDAGENCY,COPYY")
	Pdata=cursor.fetchall()
	Pamounts={}
	CEtotal=0
	
	# Index data by partner/agency/year totals and overall year totals
	for r in Pdata:
		Pamounts[r['PARTNER']+r['FUNDAGENCY']+str(r['COPYY'])]=r['SUM(CODEAMOUNT)']
		CEtotal+=r['SUM(CODEAMOUNT)']
	
	# Get overall totals to calculate proportion to be modeled back for 2007-2009 COP years and for NA awards
	cursor.execute("SELECT SUM(CODEAMOUNT) from COPs where COPCC LIKE '" + country + "' and COPYY between 2010 and " + str(Assumptions['Years'][-1]) + " and PARTNERLOCATION='International' and BUDGETCODE='TOTL'")
	TOTint=cursor.fetchall()
	if TOTint[0]['SUM(CODEAMOUNT)']==None:
		rate=0
	else:
		rate=CEtotal/TOTint[0]['SUM(CODEAMOUNT)']
	return {'Partner': Pamounts, 'Average': rate}

# Function gathers exclusions for equipment based on motor vehicle purchases for each partner by agency. Data for 2013-2015 available. Data for 2007-2012 utilize percentage rates. Structure returned is {'Partner': {<partnername><agency><year>: <amount>, ...n}, 'Average': <rate>}
def CalculateMotorVehicles(country):
	# Fetch data
	cursor.execute("SELECT COPYY,PARTNER,FUNDAGENCY,SUM(CODEAMOUNT) from CrossCut WHERE COPCC LIKE '" + country + "' and COPYY between 2012 and " + str(Assumptions['Years'][-1]) + " and PARTNERLOCATION='International' and CATEGORY='Motor Vehicles: Purchased' group by COPYY,PARTNER,FUNDAGENCY order by PARTNER,FUNDAGENCY,COPYY")
	Pdata=cursor.fetchall()
	if len(Pdata)==0:
		return {'Partner': [], 'Average': 0}
	Pamounts={}
	Vehicletotal=0
	
	# Index data by partner/agency/year totals and overall year totals
	for r in Pdata:
		Pamounts[r['PARTNER']+r['FUNDAGENCY']+str(r['COPYY'])]=r['SUM(CODEAMOUNT)']
		Vehicletotal+=r['SUM(CODEAMOUNT)']
	
	# Get overall totals to calculate proportion to be modeled back for 2007-2009 COP years and for NA awards
	cursor.execute("SELECT SUM(CODEAMOUNT) from COPs where COPCC LIKE '" + country + "' and COPYY between 2012 and " + str(Assumptions['Years'][-1]) + " and PARTNERLOCATION='International' and BUDGETCODE='TOTL'")
	TOTint=cursor.fetchall()
	rate=Vehicletotal/TOTint[0]['SUM(CODEAMOUNT)']
	return {'Partner': Pamounts, 'Average': rate}

# Function gathers exclusions for equipment based on Laboratory Infrastructure for each partner by agency. Data for all years available. Structure returned is {'Partner': {<partnername><agency><year>: <amount>, ...n}}
def CalculateLabEquipment(EquipAssumption,country):
	# Fetch data
	cursor.execute("SELECT COPYY,PARTNER,FUNDAGENCY,SUM(CODEAMOUNT) from COPs WHERE COPCC LIKE '" + country + "' and PARTNERLOCATION='International' and BUDGETCODE='HLAB' group by COPYY,PARTNER,FUNDAGENCY order by PARTNER,FUNDAGENCY,COPYY")
	Pdata=cursor.fetchall()
	Pamounts={}
	Equiptotal=0
	
	# Index data by partner/agency/year totals and overall year totals
	for r in Pdata:
		Pamounts[r['PARTNER']+r['FUNDAGENCY']+str(r['COPYY'])]=r['SUM(CODEAMOUNT)']*EquipAssumption
		Equiptotal+=r['SUM(CODEAMOUNT)']*EquipAssumption
	#print Pamounts
	return {'Partner': Pamounts}

def CalculateARVExclusions(country):
	# Fetch data
	cursor.execute("SELECT COPYY,PARTNER,FUNDAGENCY,SUM(CODEAMOUNT) from COPs WHERE COPCC LIKE '" + country + "' and PARTNERLOCATION='International' and BUDGETCODE='HTXD' group by COPYY,PARTNER,FUNDAGENCY order by PARTNER,FUNDAGENCY,COPYY")
	Pdata=cursor.fetchall()
	Pamounts={}
	ARVtotal=0
	
	# Index data by partner/agency/year totals and overall year totals
	for r in Pdata:
		Pamounts[r['PARTNER']+r['FUNDAGENCY']+str(r['COPYY'])]=r['SUM(CODEAMOUNT)']
		ARVtotal+=r['SUM(CODEAMOUNT)']
	#print Pamounts
	return {'Partner': Pamounts}

# Function calculates the propotionate breakouts of partnerlocations for allocating unallocated funding in the COPs. Structure returned is {'Main': {'IOs': <proportion>, 'Universities': <proportion>}}
def CalculateOrgTypeRatios(country):
	# Fetch data
	cursor.execute("SELECT PARTNERLOCATION,ORGTYPE,SUM(CODEAMOUNT) from COPs WHERE COPCC LIKE '" + country + "' and COPYY BETWEEN " + str(Assumptions['Years'][0]) + " and " + str(Assumptions['Years'][-1]) + " and BUDGETCODE='TOTL' and PARTNERLOCATION!='NA' and PARTNERLOCATION IS NOT NULL and CODEAMOUNT>0 group by PARTNERLOCATION,ORGTYPE order by PARTNERLOCATION,ORGTYPE")
	Odata=cursor.fetchall()
	Atotals=0
	MAINtotals={'IOs': 0, 'University': 0}
	for row in Odata:
		L=row['PARTNERLOCATION']
		O=row['ORGTYPE']
		A=row['SUM(CODEAMOUNT)']
		Atotals+=A
		if L=="International":
			if O=="University":
				MAINtotals['University']+=A
			else:
				MAINtotals['IOs']+=A
	MAINprops={'IOs': 0, 'University': 0}
	
	for Otype, Amount in MAINtotals.items():
		MAINprops[Otype]=Amount/Atotals
	#print MAINprops
	return {'Main': MAINprops}
	
# As individual partners are sometimes variously assigned different organizational types, this function gets a single Orgtype per partner based on what they have received the most funding as. Structure returned is {'Partner': {<partner>: <orgtype>,...n}}
def GetOrgTypes():
	cursor.execute("SELECT PARTNER,ORGTYPE,SUM(CODEAMOUNT) from COPs WHERE PARTNERLOCATION='International' and BUDGETCODE='TOTL' group by PARTNER,ORGTYPE order by PARTNER,SUM(CODEAMOUNT)")
	Pdata=cursor.fetchall()
	Ptypes={}
	
	# Index data by partner
	for r in Pdata:
		Ptypes[r['PARTNER']]=r['ORGTYPE']
	return {'Partner': Ptypes}
 
# Gets NICRA rates for Universities and voluntarily disclosed rates from organizations (confidential). Structure returned is {'Partner': {<partner><year>OnCampus: <rate>, <partner><year>OffCampus: <rate>,...n}, 'Averages': {<year>OnCampus: <rate>, <year>OffCampus: <rate>}}
def GetNICRAs():
	NICRAFiles = ['NICRAs-public.csv','NICRAs-confidential.csv']
	Prates={}
	Aratelists={}
	Arates={}
	AllYears={'OnCampus':[],'OffCampus':[]}
	for N in NICRAFiles:
		try:
			with open('./Data/'+N, 'r') as f:
				reader = csv.reader(f)
				next(reader)
				for row in reader:
					if int(row[1])>=Assumptions['Years'][0] and int(row[1])<=Assumptions['Years'][-1]:
						OnRate=Decimal(row[2].strip())
						OffRate=Decimal(row[3].strip())
						AllYears['OnCampus'].append(OnRate)
						AllYears['OffCampus'].append(OffRate)
						Prates[row[0]+str(row[1])+'OnCampus']=OnRate
						Prates[row[0]+str(row[1])+'OffCampus']=OffRate
						try:
							Aratelists[str(row[1])+'OnCampus'].append(OnRate)
							Aratelists[str(row[1])+'OffCampus'].append(OffRate)
						except KeyError:
							Aratelists[str(row[1])+'OnCampus']=[]
							Aratelists[str(row[1])+'OffCampus']=[]
							Aratelists[str(row[1])+'OnCampus'].append(OnRate)
							Aratelists[str(row[1])+'OffCampus'].append(OffRate)
		except IOError:
			continue
	print('***********Applied NICRA Rates*************')
	for key in sorted(Aratelists):
		Arates[key]=sum(Aratelists[key])/len(Aratelists[key])
		print(key + ': ' + str(round(sum(Aratelists[key])/len(Aratelists[key])*100,2)) + '%')
	print('All Years Average Scenarios A/B: ' + str(round(sum(AllYears['OnCampus'])/len(AllYears['OnCampus'])*100,2)) + '%')
	print('All Years Average Scenario C: ' + str(round(sum(AllYears['OffCampus'])/len(AllYears['OffCampus'])*100,2)) + '%')
	print('********End Applied NICRA Rates************')
	return {'Partner': Prates, 'Averages': Arates}

# This is the main implementation of the model for IOs and Universities
def PartnerModel(country):
	cursor.execute("SELECT COPYY,PARTNER,FUNDAGENCY,SUM(CODEAMOUNT) from COPs WHERE COPCC LIKE '" + country + "' and COPYY BETWEEN " + str(min(Assumptions['Years'])) + " and "  + str(max(Assumptions['Years'])) + " and PARTNERLOCATION='International' and BUDGETCODE!='TOTL' and CODEAMOUNT>0 group by COPYY,PARTNER,FUNDAGENCY order by COPYY,PARTNER,FUNDAGENCY")
	Pdata=cursor.fetchall()
	global Totals
	global Exclusions
	global Scenarios
	
	for row in Pdata:
		P = row['PARTNER']
		A = row['FUNDAGENCY']
		Y = str(row['COPYY'])
		Ptotal = row['SUM(CODEAMOUNT)']
		
		# Calcuate Exclusions and Enter into the Exclusions Dictionary
		SubExclusion = SubPartnerExclusion(Ptotal,P,A,Y);
		Exclusions['Sub-Awards'][Y]+=SubExclusion
		CapitalExclusion = CapitalExpenditureExclusion(Ptotal,P,A,Y);
		Exclusions['Capital Expenditures'][Y]+=CapitalExclusion
		VehicleExclusion = MotorVehicleExclusion(Ptotal,P,A,Y);
		Exclusions['Motor Vehicles'][Y]+=VehicleExclusion
		LabExclusion = LaboratoryEquipmentExclusion(P,A,Y);
		Exclusions['Lab Equipment'][Y]+=LabExclusion
		ARVExclusion = ARVDrugExclusion(P,A,Y);
		Exclusions['ARV Drugs'][Y]+=ARVExclusion
		
		# Calculate the NEC total
		NEC = Ptotal-SubExclusion-CapitalExclusion-VehicleExclusion-LabExclusion-ARVExclusion
		
		# Enter Total and NEC amounts into Scenarios Dictionary
		Totals['Total Funding'][Y]+=Ptotal
		Totals['NEC'][Y]+=NEC
		
		# Scenario Scenarios
		for S in Assumptions['Scenarios']:
			Scenarios[S][Y] += CalculateIndirects(Ptotal,NEC,S,P,A,Y);
		#print P + ': ' + A + ': ' + str(Y) + ': ' + str(Ptotal) + ': ' + str(NEC)
	
# This is the main implementation of the model for Not Available (NA) allocations
def NAModel(country):
	# Fetch NA data
	cursor.execute("SELECT COPYY,SUM(CODEAMOUNT) from COPs WHERE COPCC LIKE '" + country + "' and COPYY BETWEEN " + str(min(Assumptions['Years'])) + " and "  + str(max(Assumptions['Years'])) + " and (PARTNERLOCATION='NA' or PARTNERLOCATION IS NULL) and BUDGETCODE!='TOTL' and CODEAMOUNT>0 group by COPYY order by COPYY")
	Pdata=cursor.fetchall()
	
	# Fetch NA Lab data
	cursor.execute("SELECT COPYY,SUM(CODEAMOUNT) from COPs WHERE COPCC LIKE '" + country + "' and COPYY BETWEEN " + str(min(Assumptions['Years'])) + " and "  + str(max(Assumptions['Years'])) + " and (PARTNERLOCATION='NA' or PARTNERLOCATION IS NULL) and BUDGETCODE='HLAB' and CODEAMOUNT>0 group by COPYY order by COPYY")
	Labdata=cursor.fetchall()
	
	# Fetch NA ARV data
	cursor.execute("SELECT COPYY,SUM(CODEAMOUNT) from COPs WHERE COPCC LIKE '" + country + "' and COPYY BETWEEN " + str(min(Assumptions['Years'])) + " and "  + str(max(Assumptions['Years'])) + " and (PARTNERLOCATION='NA' or PARTNERLOCATION IS NULL) and BUDGETCODE='HTXD' and CODEAMOUNT>0 group by COPYY order by COPYY")
	ARVdata=cursor.fetchall()
	
	# Lab Exclusions
	Lexclude={}
	for row in Labdata:
		Lexclude[str(row['COPYY'])]=row['SUM(CODEAMOUNT)']*Assumptions['EquipAssumption']
	
	# ARV Exclusions
	Aexclude={}
	for row in ARVdata:
		Aexclude[str(row['COPYY'])]=row['SUM(CODEAMOUNT)']
	
	global Totals
	global Exclusions
	global Scenarios
	
	Scenes = []
	for S in Assumptions['Scenarios']:
		Scenes.append(S)

	for row in Pdata:
		MAINS={'University': 0,'IOs': 0}
		Y = str(row['COPYY'])
		T = row['SUM(CODEAMOUNT)']
		A = 'Redacted'
		P = 'Not Available'
		
		# Calculate Proportional Totals for Calculations
		MAINS['University']=CalculateNAAmounts(T,'University','Main');
		MAINS['IOs']=CalculateNAAmounts(T,'IOs','Main');
		
		NAAllocationTotals['IO']+=MAINS['IOs']
		NAAllocationTotals['Universities']+=MAINS['University']
		
		for O, T in MAINS.items():
			# Calcuate Exclusions and Enter into the Exclusions Dictionary
			SubExclusion = SubPartnerExclusion(T,P,A,Y);
			Exclusions['Sub-Awards'][Y]+=SubExclusion
			CapitalExclusion = CapitalExpenditureExclusion(T,P,A,Y,True);
			Exclusions['Capital Expenditures'][Y]+=CapitalExclusion
			VehicleExclusion = MotorVehicleExclusion(T,P,A,Y,True);
			Exclusions['Motor Vehicles'][Y]+=VehicleExclusion
			ARVExclusion = ARVDrugExclusion(P,A,Y);
			Exclusions['ARV Drugs'][Y]+=ARVExclusion
			try:
				LabExclusion = CalculateNAAmounts(Lexclude[str(Y)],O,'Main');
			except KeyError:
				LabExclusion = 0
			Exclusions['Lab Equipment'][Y]+=LabExclusion
			try:
				ARVExclusion = CalculateNAAmounts(Aexclude[str(Y)],O,'Main');
			except KeyError:
				ARVExclusion = 0
			Exclusions['ARV Drugs'][Y]+=ARVExclusion

			# Calculate the MTDC + Indirects total
			NEC = T-SubExclusion-CapitalExclusion-VehicleExclusion-LabExclusion-ARVExclusion
		
			# Enter Total and NEC amounts into Scenarios Dictionary
			Totals['Total Funding'][Y]+=T
			Totals['NEC'][Y]+=NEC
		
			# Scenario Scenarios
			for S in Scenes:
				Scenarios[S][Y] += CalculateIndirects(T,NEC,S,P,A,Y,O);

# Basic exlusion for sub-awards
def SubPartnerExclusion(Amount,Partner,Agency,Year):
	if Partner+Agency in SubRetentionRates['Partner']:
		Total = Amount*(1-SubRetentionRates['Partner'][Partner+Agency])*Modifiers['Sub-Awards']
		#print "Found Partner"
	elif Agency in SubRetentionRates['Agency']:
		Total = Amount*(1-SubRetentionRates['Agency'][Agency])*Modifiers['Sub-Awards']
		#print "Found Agency"
	else:
		Total = Amount*(1-SubRetentionRates['Average'])*Modifiers['Sub-Awards']
		#print "No Rate Found - Using Assumption: " + repr(Agency)
	return Total

# Function calculates total exclusions for Capital Expenditures. NA variable is necessary to force use of averages on NA amounts. Returns total to be excluded
def CapitalExpenditureExclusion(Amount,Partner,Agency,Year,NA=False):
	if int(Year)<2010 or NA==True:
		Total = Amount*CapitalExpenditures['Average']*Modifiers['Capital Expenditures']
		#print "Using Average: " + str(CapitalExpenditures['Average'])
	elif Partner+Agency+Year in CapitalExpenditures['Partner']:
		Total = CapitalExpenditures['Partner'][Partner+Agency+Year]*Modifiers['Capital Expenditures']
		#print "Found Partner"
	else:
		Total=0
	return Total

# Function calculates total exclusions for Motor Vehicles. NA variable is necessary to force use of averages on NA amounts. Returns total to be excluded
def MotorVehicleExclusion(Amount,Partner,Agency,Year,NA=False):
	if int(Year)<2013 or NA==True:
		Total = Amount*MotorVehicles['Average']*Modifiers['Motor Vehicles']
		#print "Using Average: " + str(MotorVehicles['Average'])
	elif Partner+Agency+Year in MotorVehicles['Partner']:
		Total = MotorVehicles['Partner'][Partner+Agency+Year]*Modifiers['Motor Vehicles']
		#print "Found Partner"
	else:
		Total=0
	return Total

# Function calculates total exclusions for Lab Equipment.
def LaboratoryEquipmentExclusion(Partner,Agency,Year):
	if Partner+Agency+str(Year) in LabEquipment['Partner']:
		Amount = LabEquipment['Partner'][Partner+Agency+str(Year)]*Modifiers['LabEquipment']
		#print "Found Partner"
	else:
		Amount = 0
	return Amount

# Function calculates total exclusions for Lab Equipment.
def ARVDrugExclusion(Partner,Agency,Year):
	if Partner+Agency+str(Year) in ARVs['Partner']:
		Amount = ARVs['Partner'][Partner+Agency+str(Year)]*Modifiers['arvs']
		#print "Found Partner"
	else:
		Amount = 0
	return Amount

# Function applies the NICRA rates based on partner, year, and scenario. Averages are used for unknown entities. Returns the total indirects.
def CalculateIndirects(Ptotal,Amount,scenario,Partner,Agency,Year,Otype=False):
	#Random generation for determining whether to asign a non-NICRA rate to proportion or partners set in assumptions
	r=random()
	if scenario=='Scenario A':
		if Partner+Year+'OnCampus' in NICRAs['Partner']:
			Nrate=NICRAs['Partner'][Partner+Year+'OnCampus']
		else:
			if r<Assumptions['NonNICRAIOs'] and Ptotal<Assumptions['NonNICRACap']:
				Nrate=0.1
			else:
				Nrate=NICRAs['Averages'][Year+'OnCampus']
	elif scenario=='Scenario B':
		if not Otype:
			Otype=OrgTypes['Partner'][Partner]
		if Otype=='University':
			if Partner+Year+'OffCampus' in NICRAs['Partner']:
				Nrate=NICRAs['Partner'][Partner+Year+'OffCampus']
			else:
				if r<Assumptions['NonNICRAIOs'] and Ptotal<Assumptions['NonNICRACap']:
					Nrate=0.1
				else:
					Nrate=NICRAs['Averages'][Year+'OffCampus']
		else:
			if Partner+Year+'OnCampus' in NICRAs['Partner']:
				Nrate=NICRAs['Partner'][Partner+Year+'OnCampus']
			else:
				if r<Assumptions['NonNICRAIOs'] and Ptotal<Assumptions['NonNICRACap']:
					Nrate=0.1
				else:
					Nrate=NICRAs['Averages'][Year+'OnCampus']
	elif scenario=='Scenario C':
		if Partner+Year+'OffCampus' in NICRAs['Partner']:
			Nrate=NICRAs['Partner'][Partner+Year+'OffCampus']
		else:
			if r<Assumptions['NonNICRAIOs'] and Ptotal<Assumptions['NonNICRACap']:
				Nrate=0.1
			else:
				Nrate=NICRAs['Averages'][Year+'OffCampus']
	elif scenario=='Assumed 20%':
		if Partner+Year+'OffCampus' in NICRAs['Partner']:
			Nrate=NICRAs['Partner'][Partner+Year+'OffCampus']
		else: 
			Nrate=0.2
	elif scenario=='Assumed 15%':
		if Partner+Year+'OffCampus' in NICRAs['Partner']:
			Nrate=NICRAs['Partner'][Partner+Year+'OffCampus']
		else:
			Nrate=0.15
	elif scenario=='Assumed 10%':
		if Partner+Year+'OffCampus' in NICRAs['Partner']:
			Nrate=NICRAs['Partner'][Partner+Year+'OffCampus']
		else: 
			Nrate=0.1
	else:
		print "Scenario entered incorrectly"
	Total = Decimal(Amount)/(1+Decimal(Nrate))*Decimal(Nrate)
	return Total

# Returns the proportion of funds allocated to IOs/Universities.
def CalculateNAAmounts(Amount,OrgType,Model):
	Total = Amount*OrgTypeRatios[Model][OrgType]
	return Total
	
if __name__ == '__main__':
	status = main()
	sys.exit(status)
