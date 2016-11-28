#############################
# Workflow - Food Security
# Scale - Landscape
# 09 May 2016
#
# input the following modules from the VS Household Survey
#
# calculate the food security indicators:
#   food utilization
#
# output the indicator at the given scale for the given time period
#############################

#################
# Setup
#################

library(reshape2)
library(dplyr)
library(lubridate)

setwd("/home/ubuntu/ci_hackathon-master/R_stuff/food_security/")  #replace with your working directory here

pg_conf <- read.csv('rds_settings.csv', stringsAsFactors=FALSE)

vs_db <- src_postgres(dbname='vitalsigns_staging', host=pg_conf$host,
                      user=pg_conf$user, password=pg_conf$pass,
                      port=pg_conf$port)

# Vital Signs Datasets
metadata <- tbl(vs_db, "curation__household") %>% data.frame
food_spending <- tbl(vs_db, "curation__household_secK1") %>% data.frame #FS 6
food_consumption <- tbl(vs_db, "curation__household_secK2") %>% data.frame(stringsAsFactors=F) #FS 9
nonfood_spending <- tbl(vs_db, "curation__household_secL") %>% data.frame #FS 7
food_insecurity <- tbl(vs_db, "curation__household_secI") %>% data.frame #FS 5
crop_production <- tbl(vs_db, "curation__agric_crops_by_field") %>% data.frame #FS 1
fruit_prodcution <- tbl(vs_db, "curation__agric_perm_crops_by_field") %>% data.frame #FS 1
livestock <- tbl(vs_db, "curation__agric_livestock") %>% data.frame #FS 2
by_prouducts <- tbl(vs_db, "curation__agric_livestock_byproduct") %>% data.frame #FS 2




# External Datasets
staple <- read.csv("staple.csv")

#################
# Define Functions
#################

foodcons <- function(df) {
  
  df$k_04[is.na(df$k_04) ] <- 0  #NA counts as 0 spending
  df$k_05a[is.na(df$k_05a) ] <- 0  #NA counts as 0 hypothetical spending
  
  food <- df %>% group_by(Household.ID) %>% summarise(food_cons = sum(k_04 + k_05a, na.rm = TRUE))
  
  # annualize
  food$food_cons <- food$food_cons / 7 * 365.24 
  
  return (food)
}

nonfoodcons <- function (df, sec_m = TRUE) {
  
  # keep the first 4 columns, while subsequently dropping every other column
  df <- df[ , c('Country', 'Landscape..', 'Household.ID', 'Data.entry.date', names(df)[grepl('_2$', names(df))])]
  
  # melt to long shape
  df <- melt(df, 
             id.vars = c("Country", "Landscape..", "Household.ID", "Data.entry.date"),
             variable.name = "nonfood.code",
             value.name = "amount.spent")
  
  #list of items measured weekly.  All other items measured monthly
  weekly <- c('l_101_2', 'l_102_2', 'l_103_2', 'l_199_2', 'l_204_2', 'l_206_2', 'l_207_2', 'l_207_2a')
  
  df[df$nonfood.code %in% weekly,'amount.spent'] <- df[df$nonfood.code %in% weekly,'amount.spent']/7*365.24
  df[!df$nonfood.code %in% weekly,'amount.spent'] <- df[!df$nonfood.code %in% weekly,'amount.spent']/31*365.24
  
  # sum valued nonfood consumption by household
  nonfood <- df %>% group_by(Household.ID) %>% summarise(nonfood_cons = sum(amount.spent, na.rm = TRUE))
  
  return(nonfood)
  
}

#################
# Staging
#################

metadata <- metadata  %>% group_by(Country, Household.ID, Landscape.., latitude, longitude) %>% summarize(Data.entry.date=mean(ymd(Data.entry.date)))

food_spending <- subset(food_spending, select = c(Country, Household.ID, k_item, k_item_code, k_04, k_05a))

food_consumption <- food_consumption %>% group_by(Country, Household.ID, Landscape..) %>% summarize(k2_8_a=mean(k2_8_a, na.rm=T), k2_8_b=mean(k2_8_b, na.rm=T),
                          k2_8_c=mean(k2_8_c, na.rm=T), k2_8_d=mean(k2_8_d, na.rm=T), k2_8_e=mean(k2_8_e, na.rm=T), k2_8_f=mean(k2_8_f, na.rm=T), k2_8_g=mean(k2_8_g, na.rm=T), k2_8_h=mean(k2_8_h, na.rm=T),
                          k2_8_i=mean(k2_8_i, na.rm=T), k2_8_j=mean(k2_8_j, na.rm=T))

#FS 7
food.cons <- foodcons(food_spending)

nonfood.cons <- nonfoodcons(nonfood_spending)

# valued non staple food consumption
food_spending$k_04[is.na(food_spending$k_04) ] <- 0
food_spending$k_05a[is.na(food_spending$k_05a) ] <- 0

nonstaple <- merge(staple[staple$non.staple == "Y",], 
                   food_spending,  by.x = "item", by.y = "k_item")

nonstaple.cons <- nonstaple %>% group_by(Household.ID) %>% summarise(staple_cons = sum(k_04 + k_05a, na.rm = TRUE))

# merge together
foodsec <- merge(nonfood.cons, food.cons, all = TRUE)
foodsec <- merge(foodsec, nonstaple.cons, all = TRUE)
foodsec <- merge(foodsec, metadata, all = TRUE)

#FS 8 Per capita food consumption in mass is missing, too

#FS 9
food_util <- merge(food_consumption, metadata, all = TRUE)

foodsec$key <- paste0(foodsec$Country, '.', foodsec$Landscape..)
food_util$key <- paste0(food_util$Country, '.', food_util$Landscape..)

#################
# Analysis
#################

foodsec.df <- data.frame()
for (k in unique(foodsec$key)){
  
  ctr <- substr(k,1,3)
  land <- substr(k,5,7)
  
  foodsec_ls <- foodsec[foodsec$Country == ctr & foodsec$Landscape.. == land, ]
  food_util_ls <- food_util[food_util$Country == ctr & food_util$Landscape.. == land, ]
  
  # get average year of survey enumeration
  yr <- year(mean(foodsec_ls$Data.entry.date))
  
  # FS 16 missing - so 'proxy' gap assessment done instead
  # FS 17 proxy gap assessment
  gap <- mean(foodsec_ls$staple_cons / foodsec_ls$food_cons, na.rm=T)
  
  # FS 18 buffer assessment
  buffer <- 1 - mean(foodsec_ls$food_cons / 
                       (foodsec_ls$food_cons + foodsec_ls$nonfood_cons), na.rm=T)
  
  # FS 19 food access score
  access <- gap * buffer
  
  # Missing FS 20, which should be combined with FS 21

  # FS21.1 daily dietary diversity score
  # sum p(consumed food item yesterday) as x / 7 for all x
  f_groups <- c("k2_8_a", "k2_8_b", "k2_8_c", "k2_8_d", "k2_8_e",
                "k2_8_f","k2_8_g",  "k2_8_h", "k2_8_i", "k2_8_j")
  
  daily <- rowSums(food_util_ls[f_groups] / 7, na.rm=T) / length(f_groups)
  
  # FS21.2 weekly dietary diversity score
  weekly <- rowSums(food_util_ls[f_groups] > 0) / length(f_groups)
  
  # FS22 calc food utilization
  utilization <- mean(daily * 0.5 + weekly * 0.5, na.rm=T)
    
  #################
  # Format Output
  #################
  
  foodsec.df1 <- data.frame(country = ctr,
                               scale = "Landscape",
                               year = yr,
                               landscape = land,
                               foodsec = NA,
                               availability = NA,
                               access = access,
                               utilization = utilization)
  
  foodsec.df <- bind_rows(foodsec.df, foodsec.df1)
}

foodsec.df.final <- merge(foodsec.df, unique(metadata[,c('Country', 'Landscape..', 'latitude', 'longitude')]), by.x=c('country', 'landscape'), by.y=c('Country', 'Landscape..'), all.x = T)

write.csv(foodsec.df.final, 'FoodSecurity.VS.Landscape.csv', row.names = F)
