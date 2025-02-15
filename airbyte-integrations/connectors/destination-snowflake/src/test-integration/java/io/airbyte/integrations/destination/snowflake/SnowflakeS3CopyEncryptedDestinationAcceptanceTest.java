package io.airbyte.integrations.destination.snowflake;

import com.fasterxml.jackson.databind.JsonNode;
import com.google.common.base.Preconditions;
import io.airbyte.commons.io.IOs;
import io.airbyte.commons.json.Jsons;
import java.nio.file.Path;

public class SnowflakeS3CopyEncryptedDestinationAcceptanceTest extends SnowflakeInsertDestinationAcceptanceTest {

  @Override
  public JsonNode getStaticConfig() {
    final JsonNode copyConfig = Jsons.deserialize(IOs.readFile(Path.of("secrets/copy_s3_encrypted_config.json")));
    Preconditions.checkArgument(SnowflakeDestinationResolver.isS3Copy(copyConfig));
    Preconditions.checkArgument(!SnowflakeDestinationResolver.isGcsCopy(copyConfig));
    return copyConfig;
  }
}
