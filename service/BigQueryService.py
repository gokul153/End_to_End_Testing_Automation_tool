from google.cloud import bigquery
from typing import List, Dict, Optional
import os
# Initialize BigQuery client
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "./clouddemokey.json"
client = bigquery.Client()

class BigQueryService:
    """
    Service class to handle BigQuery data operations.
    """
    def get_hospitals(self, feild_name: Optional[str] = None) -> List[Dict]:
        """
        Fetches hospital data from the BigQuery table.
        Args:
            hospital_name: An optional hospital name to filter by.
        Returns:
            A list of dictionaries with the query results.
        """
        queryMain = "SELECT "
        queryEnd = " FROM `endtoendtestingtool.automationbrdhealthcare.testdata` LIMIT 10"
        if feild_name:
            query = queryMain + feild_name + queryEnd
        
       
        try:
            print(query)
            query_job = client.query(query)
            rows = query_job.result()
            
            data = [dict(row) for row in rows]
            
            return data
        except Exception as e:
            print("fetching from bigquery failed")
            raise e