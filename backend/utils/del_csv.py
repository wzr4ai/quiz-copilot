import pandas as pd

# 读取 CSV 文件
df = pd.read_csv('backend/high_work.csv')

# 删除列（例如删除 'column_name' 列）
df = df.drop(columns=['Bank'])

# 或者按列索引删除（例如删除第2列，从0开始计数）
# df = df.drop(df.columns[1], axis=1)

# 保存文件
df.to_csv('done.csv', index=False)
print("列已删除并保存为新文件")