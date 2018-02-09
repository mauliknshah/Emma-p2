from pyspark.sql import SQLContext


from pyspark.ml.classification import LogisticRegression
from pyspark.ml.evaluation import MulticlassClassificationEvaluator

from pyspark.ml.feature import *
from pyspark import SparkContext
from pyspark.sql.functions import udf,col,split
import argparse

from pyspark.ml.linalg import Vectors, VectorUDT



import requests
import os;
from pyspark.sql.types  import *
import sys
PATH = "https://storage.googleapis.com/uga-dsp/project2/data/bytes"

sc = SparkContext()#"local[*]",'pyspark tuitorial'
sqlContext = SQLContext(sc)

def merge_col(*x):
	temp = list();
	for i in x:
		temp.extend(i)
	return temp


def prediction_and_label(model,dataset):
	predictions = model.transform(dataset)
	predictions.printSchema()
	evaluator = MulticlassClassificationEvaluator(
    labelCol="label", predictionCol="prediction", metricName="accuracy")
	accuracy = evaluator.evaluate(predictions)
	return (accuracy);


def tfidf_processor(df,inputCol="text",outputCol="tfidf_vector"):
	hashingTF = HashingTF(inputCol=inputCol, outputCol=outputCol, numFeatures=400)
	df = hashingTF.transform(df)
	#idf = IDF(inputCol="raw_features", outputCol=outputCol,minDocFreq=3)
	#idfModel = idf.fit(tf)
	#df = idfModel.transform(tf)
	return df

def count_vectorizer_processor(df,inputCol="merge_text_array",outputCol="features"):
	cv_train = CountVectorizer(inputCol=inputCol, outputCol=outputCol, vocabSize=3, minDF=2.0)
	model = cv_train.fit(df)
	df = model.transform(df)
	return df




def word2ved_processor(df):
	wv_train =  Word2Vec(inputCol="text",outputCol="vector").setVectorSize(20)
	model = wv_train.fit(df)
	df = model.transform(df)
	return df


def ngram_processor(df,n_count=3):
	cols = list();
	for i in range(2,n_count+1):
		cols.append("text_ngram_"+str(i))
		ngram = NGram(n=i, inputCol="text", outputCol="text_ngram_"+str(i))
		df = ngram.transform(df)

	merge_udf = udf(merge_col)
	df = df.withColumn("merge_text",merge_udf("text","text_ngram_2","text_ngram_3"))
	df = df.withColumn("merge_text_array",split(col("merge_text"), ",")).drop(col("merge_text"))

	return df


def fetch_url(x,path):
	class_label = x[1][1]
	url = x[1][0]
	fetch_url = path+"/"+url+".bytes"
	text = requests.get(fetch_url).text
	entries = text.split(os.linesep)
	entries = [(i.strip().replace("'",""),class_label) for i in  entries]
	return entries;

def open_row(x):
	entries = [i for i in x[0].split(' ')]
	entries.append(x[1])
	return entries
	

def clean(x):
	count = 0
	temp = x[0].split(' ')[1:]
	for i in range(0,len(temp)):
		if temp[i] == '00' or temp[i] == '??':
			count = count + 1
	if count == len(temp):
		return None
	
	
	
	return (temp,x[1])


def one_vs_all(x,current_class):
		if x[0] !=current_class:
			return(Vectors.dense(x[1]),0)
		else:
			return (Vectors.dense(x[1],1))

parser = argparse.ArgumentParser(description='Welcome to Team Emma.')
parser.add_argument('-a','--train_x', type=str,
                    help='training x set')
parser.add_argument( '-b','--train_y' ,help='training y set')
parser.add_argument('-c','--test_x', type=str,
                    help='testing x set')
parser.add_argument('-d','--test_y', type=str,
                    help='testing y set')
parser.add_argument('-e','--path', type=str,
                    help='path to folder')

args = vars(parser.parse_args())
#print(args)
rdd_train_x = sc.textFile(args['train_x']).zipWithIndex().map(lambda l:(l[1],l[0]))
rdd_train_y = sc.textFile(args['train_y']).zipWithIndex().map(lambda l:(float(l[1]-1),l[0]));
rdd_test_x = sc.textFile(args['test_x']).zipWithIndex().map(lambda l:(l[1],l[0]));
rdd_test_y = sc.textFile(args['test_y']).zipWithIndex().map(lambda l:(float(l[1]-1),l[0]));
rdd_train = rdd_train_x.join(rdd_train_y)
rdd_test = rdd_test_x.join(rdd_test_y)
#take 30 due to gc overhead
rdd_train = rdd_train.flatMap(lambda l :fetch_url(l,args['path'])).map(lambda l:clean(l)).filter(lambda l:l !=None)
#rdd_train = sc.parallelize(rdd_train)
print("Training Zeros" + str(rdd_train.count()));
print("Download complete");
rdd_test= rdd_test.flatMap(lambda l :fetch_url(l,args['path'])).map(lambda l:clean(l)).filter(lambda l: l!=None)
#rdd_test = sc.parallelize(rdd_test)
print("Test Zeros" + str(rdd_test.count()));


print("Download complete")



df_train_original = sqlContext.createDataFrame(rdd_train,schema=["text","class_label"])
df_test_original = sqlContext.createDataFrame(rdd_test,schema=["text","class_label"])
df_train_original = df_train_original.repartition(30)
df_test_original = df_test_original.repartition(30) 

#df_train_orignal ,df_train_orignal_validate =df_train_orignal.randomSplit([0.7,0.3])


df_train_original.printSchema()

df_train_original.cache()
df_test_original.cache()

## word2vec code

#df_train_word2vec = word2ved_processor(df_train_orignal)
#df_test_word2vec = word2ved_processor(df_test_orignal)
#df_train_word2vec.show()
#df_train_word2vec.show()


##ngram code 
#df_train_ngram = ngram_processor(df_train_orignal,n_count=3);
#df_test_ngram = ngram_processor(df_test_orignal,n_count=3)

#df_train_ngram.show()
#df_test_ngram.show();

#count vectorizer + ngram
#df_train_vectorizer = count_vectorizer_processor(df_train_ngram,"merge_text_array")
#df_test_vectorizer = count_vectorizer_processor(df_test_ngram,"merge_text_array")

df_tfidf_train = tfidf_processor(df_train_original,"text","tfidf_vector");
print("now processing tf-idf");
df_tfidf_train.count();
df_tfidf_test = tfidf_processor(df_test_original,"text","tfidf_vector");
df_tfidf_test.count();
df_tfidf_test = df_tfidf_test.rdd.map(lambda l:[l[1],l[-1].toArray()])
df_tfidf_train= df_tfidf_train.rdd.map(lambda l:[l[1],l[-1].toArray()])
print("processing complete");

#print(df_tfidf_test.take(20)[-1][-1])
#df_train_vectorizer.show();
#df_test_vectorizer.show();
#df_tfidf_train.show()
#df_tfidf_test.show()


# Split data approximately into training (60%) and test (40%)"""
training_0,testing_0=df_tfidf_train.map(lambda l: one_vs_all(l,0)).randomSplit([0.7,0.3]);
training_0 = sqlContext.createDataFrame(training_0,schema=["features","label"])
testing_0 = sqlContext.createDataFrame(testing_0,schema=["features","label"])

training_1,testing_1=df_tfidf_train.map(lambda l: one_vs_all(l,1)).randomSplit([0.7,0.3]);
training_1 = sqlContext.createDataFrame(training_1,schema=["features","label"])
testing_1 = sqlContext.createDataFrame(testing_1,schema=["features","label"])
training_2,testing_2=df_tfidf_train.map(lambda l : one_vs_all(l,2)).randomSplit([0.7,0.3]);
training_2 = sqlContext.createDataFrame(training_2,schema=["features","label"])
testing_2 = sqlContext.createDataFrame(testing_2,schema=["features","label"])
training_3,testing_3=df_tfidf_train.map(lambda l : one_vs_all(l,3)).randomSplit([0.7,0.3]);
training_3 = sqlContext.createDataFrame(training_3,schema=["features","label"])
testing_3 = sqlContext.createDataFrame(testing_3,schema=["features","label"])
training_4,testing_4=df_tfidf_train.map(lambda l : one_vs_all(l,4)).randomSplit([0.7,0.3]);
training_4 = sqlContext.createDataFrame(training_4,schema=["features","label"])
testing_4 = sqlContext.createDataFrame(testing_4,schema=["features","label"])









model_0 = LogisticRegression(maxIter=1000, regParam=0.3, elasticNetParam=0.8,labelCol="label", featuresCol="features").fit(training_0)
model_1 = LogisticRegression(maxIter=1000, regParam=0.3, elasticNetParam=0.8,labelCol="label", featuresCol="features").fit(training_1)
model_2= LogisticRegression(maxIter=1000, regParam=0.3, elasticNetParam=0.8,labelCol="label", featuresCol="features").fit(training_2)
model_3= LogisticRegression(maxIter=1000, regParam=0.3, elasticNetParam=0.8,labelCol="label", featuresCol="features").fit(training_3)
model_4= LogisticRegression(maxIter=1000, regParam=0.3, elasticNetParam=0.8,labelCol="label", featuresCol="features").fit(training_4)
value_0 = prediction_and_label(model_0,training_0)
value_1 = prediction_and_label(model_1,training_1)
value_2  = prediction_and_label(model_2,training_2)
value_3  = prediction_and_label(model_3,training_3)
value_4  = prediction_and_label(model_4,training_4)

value_01= prediction_and_label(model_0,testing_0)
value_11 = prediction_and_label(model_1,testing_1)
value_21  = prediction_and_label(model_2,testing_2)
value_31  = prediction_and_label(model_3,testing_3)
value_41  = prediction_and_label(model_4,testing_4)




print(str(value_0)+":" + str(value_1) + ":" + str(value_2) +";"+  str(value_3) + ";"+ str(value_4))
print(str(value_01)+":" + str(value_11) + ":" + str(value_21) +";"+  str(value_31) + ";"+ str(value_41))

sys.exit(-1)



# Train a naive Bayes model.
#model = NaiveBayes.train(training, 0.7)

# Make prediction and test accuracy.
predictionAndLabel = training.map(lambda p: (model.predict(p.features), p.label))
accuracy = 1.0 * predictionAndLabel.filter(lambda pl: pl[0] == pl[1]).count() / training.count()
#print(predictionAndLabel.map(lambda x:x[0]).collect())
print('model accuracy {}'.format(accuracy))


#print(df_tfidf_test.take(20)[-1][-1])
#df_train_vectorizer.show();
#df_test_vectorizer.show();
#df_tfidf_train.show()
#df_tfidf_test.show()