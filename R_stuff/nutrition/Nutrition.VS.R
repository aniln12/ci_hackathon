#############################
# Workflow - Nutrition
# scale - Individual, Landscape
#
# input the following modules from the VS Server
#   hh_sec_a, 
#   hh_sec_b, 
#   hh_sec_u

# calculate the four nutrition indicators:
#   % stunted
#   % wasted
#   % underweight
#   % overweight
#
# output the 4 indicators at the given scale for the given time period
#############################

#################
# Setup
#################
# libraries
# Utility package for CI Vital Signs project

library(dplyr)
library(zoo)

setwd("/home/ubuntu/ci_hackathon-master/R_stuff/Nutrition")  # replace with your working directory here

pg_conf <- read.csv('rds_settings.csv', stringsAsFactors=FALSE)

vs_db <- src_postgres(dbname='vitalsigns_staging', host=pg_conf$host,
                      user=pg_conf$user, password=pg_conf$pass,
                      port=pg_conf$port)

# Read datasets and only keep variables for nutrition thread
hh_sec_a <- tbl(vs_db, build_sql("SELECT * FROM curation__household")) %>%
  select(Country, Region, `Landscape #`, District, `Household ID`, `Data entry date`) %>%
  data.frame

hh_sec_b <- tbl(vs_db, build_sql('SELECT * FROM "curation__household_secB"')) %>%
  select(`Household ID`, `Individual ID`, hh_b02, hh_b03) %>% # Sex, age
  data.frame

hh_sec_u <- tbl(vs_db, build_sql('SELECT * FROM "curation__household_secU"')) %>%
  select(`Household ID`, `Individual ID`, u1_01, u2_01, u3_01, u4_01, u5_01, u6_01) %>% # weight=hh_v03; lenhei=hh_v04;  armc=hh_v07; measure=hh_v05 
  data.frame

landscape <- tbl(vs_db, 'landscape') %>%
  data.frame
    
# Restore reference data sets
weianthro <- read.table("WHO Anthro reference tables/weianthro.txt", header=T)
lenanthro <- read.table("WHO Anthro reference tables/lenanthro.txt", header=T)
wflanthro <- read.table("WHO Anthro reference tables/wflanthro.txt", header=T)
wfhanthro <- read.table("WHO Anthro reference tables/wfhanthro.txt", header=T)
hcanthro <- read.table("WHO Anthro reference tables/hcanthro.txt", header=T)
acanthro <- read.table("WHO Anthro reference tables/acanthro.txt", header=T)
bmianthro <- read.table("WHO Anthro reference tables/bmianthro.txt", header=T)
ssanthro <- read.table("WHO Anthro reference tables/ssanthro.txt", header=T)
tsanthro <- read.table("WHO Anthro reference tables/tsanthro.txt", header=T)

# Merge datasets into one "nutrition" dataset
nutrition <- merge(hh_sec_a, hh_sec_b, 
                   by = "Household.ID", all = TRUE)
nutrition <- merge(nutrition, hh_sec_u, 
                   by = c("Household.ID", "Individual.ID"), all = TRUE)

# Household and individual ID
# N23. Gender (M=1, F=2)
nutrition$sex <- as.integer(nutrition$hh_b02)
nutrition$hh_b02 <- NULL

# N24. Age
nutrition$hh_b03 <- as.Date(substr(nutrition$hh_b03, 1, 10))
# ISSUE32 change to Date of the interview when added
nutrition$Data.entry.date <- as.Date(nutrition$Data.entry.date)

# age in months
# ISSUE32 change to Date of the interview when added
nutrition$age <- (as.yearmon(nutrition$Data.entry.date) - 
  as.yearmon(nutrition$hh_b03)) * 12

nutrition$intyr <- as.integer(format(nutrition$Data.entry.date, "%Y"))

# N25. Height / N26. Weight / N27. Upper arm circumference

names(nutrition)[names(nutrition) == "u2_01"] <- "weight"
names(nutrition)[names(nutrition) == "u3_01"] <- "lenhei"
names(nutrition)[names(nutrition) == "u5_01"] <- "armc"
names(nutrition)[names(nutrition) == "u4_01"] <- "measure"

nutrition$measure[nutrition$measure == "STANDING"] <- "1"
nutrition$measure[nutrition$measure == "LYING DOWN"] <- "2"

# ISSUE32 need to add date of interview when it is added
vars <- c("Country", "Region", "District", "Landscape..", 
          "Household.ID", "Individual.ID",  "intyr", "age", 
          "weight", "lenhei", "armc", "measure", "sex")

nutrition <- nutrition[ , vars]

#################
# Analysis
#################

nutrition_df <- data.frame(country = character(), 
                           scale = character(), 
                           year = integer(), 
                           landscape = integer(),
                           underweight = double(),
                           underweight.severe = double(),
                           stunting = double(),
                           stunting.severe = double(),
                           wasting = double(),
                           wasting.severe = double(),
                           overweight = double(),
                           overweight.severe =  double())


outfile_slice <- paste("igrowup_outfile")
nutrition.subset <- nutrition[nutrition$age<60,]

source('igrowup_standard.r')

igrowup.standard(mydf = nutrition.subset,
               sex = sex,
               age = age,
               age.month = T, 
               weight = weight, 
               lenhei = lenhei,
               measure = measure, 
               armc = armc)

matz$zlen[matz$flen==1] <- NA
matz$zwei[matz$fwei==1] <- NA
matz$zwfl[matz$fwfl==1] <- NA
matz <- matz[matz$age > 6, ]

nutrition_df <- matz[,c('Country', 'Landscape..', 'Household.ID', 'Individual.ID', 'zlen', 'zwei', 'zwfl')] 

nutrition_df$stunting <- ifelse(nutrition_df$zlen < -2, 1, 0)
nutrition_df$severe_stunting <- ifelse(nutrition_df$zlen < -3, 1, 0)
nutrition_df$underweight <- ifelse(nutrition_df$zwei < -2, 1, 0)
nutrition_df$severe_underweight <- ifelse(nutrition_df$zwei < -3, 1, 0)
nutrition_df$wasting <- ifelse(nutrition_df$zwfl < -2, 1, 0)
nutrition_df$severe_wasting <- ifelse(nutrition_df$zwfl < -3, 1, 0)
nutrition_df$overweight <- ifelse(nutrition_df$zwei > 1, 1, 0)

nutrition_df$CIAF <- as.numeric(nutrition_df$stunting | nutrition_df$underweight | nutrition_df$wasting)

nutrition_df$LandscapeCode <- paste(nutrition_df$Country, nutrition_df$Landscape.., sep='-')

landscape$LandscapeCode <- paste(landscape$country, landscape$landscape_no, sep='-')
landscape$latitude <- rowMeans(landscape[, c('lower_right_latitude', 'lower_left_latitude', 'upper_right_latitude', 'upper_left_latitude')], na.rm=T)
landscape$longitude <- rowMeans(landscape[, c('lower_right_longitude', 'lower_left_longitude', 'upper_right_longitude', 'upper_left_longitude')], na.rm=T)

nutrition_coords <- merge(nutrition_df, landscape[,c('LandscapeCode', 'latitude', 'longitude')], by='LandscapeCode', all.x=T)
nutrition_coords$LandscapeCode <- NULL

write.csv(nutrition_coords, 'Nutrition.Individual.csv', row.names = F)

nutrition_landscape <- group_by(nutrition_coords, Country, Landscape.., latitude, longitude) %>% 
  summarise(mean_zlen=mean(zlen, na.rm=T), mean_zwei=mean(zwei, na.rm=T), mean_zwfl=mean(zwfl, na.rm=T),
            percent_stunted=mean(stunting, na.rm=T)*100, percent_severe_stunted=mean(severe_stunting, na.rm=T)*100,
            percent_underweight=mean(underweight, na.rm=T)*100, percent_severe_underweight=mean(severe_underweight, na.rm=T)*100,
            percent_wasting=mean(wasting, na.rm=T)*100, percent_server_wasting=mean(severe_wasting, na.rm=T)*100,
            percent_overweight=mean(overweight, na.rm=T)*100, percent_Composite_Index_Anthropometric_Failure=mean(CIAF, na.rm=T)*100)

write.csv(nutrition_landscape, 'Nutrition.Landscape.csv', row.names = F)

